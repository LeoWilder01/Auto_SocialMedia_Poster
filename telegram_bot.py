import os
import io
import asyncio
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, InputFile


class TelegramApprover:
    def __init__(self, bot_token: str, chat_id: str):
        self.bot = Bot(token=bot_token)
        self.chat_id = int(chat_id)

    async def send_for_approval(self, post_text: str, image_data: bytes = None) -> dict:
        """
        Send post and image for approval with Approve/Reject buttons.
        User can respond via Telegram OR PowerShell.

        Returns:
            dict with 'approved' (bool) and 'tone' (str, if rejected)
        """
        # Send the image first if provided
        if image_data:
            image_file = InputFile(io.BytesIO(image_data), filename="preview.webp")
            await self.bot.send_photo(
                chat_id=self.chat_id,
                photo=image_file,
                caption="🖼 Generated image preview"
            )

        # Build preview message
        preview = f"📝 **New Post for Review**\n\n{post_text}\n\n"
        preview += f"📊 Characters: {len(post_text)}/500"

        # Send text with approval buttons
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Approve", callback_data="approve"),
                InlineKeyboardButton("❌ Reject", callback_data="reject"),
            ]
        ])

        message = await self.bot.send_message(
            chat_id=self.chat_id,
            text=preview,
            reply_markup=keyboard,
        )

        # Print terminal prompt
        print("\n" + "=" * 50)
        print("Respond here OR in Telegram:")
        print("  y = approve")
        print("  n = reject")
        print("=" * 50)

        # Wait for response from either Telegram or terminal
        response = await self._wait_for_dual_input(message.message_id)

        if response == "approve":
            await self.bot.send_message(self.chat_id, "✅ Post approved! Publishing...")
            return {"approved": True, "tone": None}

        # User rejected - ask for tone preference
        return await self._ask_tone_preference()

    async def _wait_for_terminal(self) -> str:
        """Wait for terminal input in a thread."""
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, input, "Your choice (y/n): ")
        response = response.strip().lower()
        if response in ("y", "yes"):
            return "approve"
        elif response in ("n", "no"):
            return "reject"
        return None  # Invalid input

    async def _wait_for_telegram(self, message_id: int) -> str:
        """Wait for Telegram callback."""
        updates = await self.bot.get_updates(limit=1)
        offset = updates[-1].update_id + 1 if updates else 0

        while True:
            updates = await self.bot.get_updates(offset=offset, timeout=5)

            for update in updates:
                offset = update.update_id + 1

                if update.callback_query:
                    callback = update.callback_query
                    if callback.message and callback.message.message_id == message_id:
                        await callback.answer()
                        return callback.data

            await asyncio.sleep(0.5)

    async def _wait_for_dual_input(self, message_id: int, timeout: int = 300) -> str:
        """Wait for input from either Telegram or terminal."""
        terminal_task = asyncio.create_task(self._wait_for_terminal())
        telegram_task = asyncio.create_task(self._wait_for_telegram(message_id))

        try:
            done, pending = await asyncio.wait(
                [terminal_task, telegram_task],
                timeout=timeout,
                return_when=asyncio.FIRST_COMPLETED
            )

            # Cancel pending tasks
            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

            if not done:
                await self.bot.send_message(self.chat_id, "⏰ Timed out waiting for response.")
                raise TimeoutError("No response received")

            # Get result from completed task
            result = done.pop().result()

            # If terminal gave invalid input, wait for Telegram
            if result is None:
                print("Invalid input. Use 'y' or 'n'. Waiting for Telegram...")
                return await self._wait_for_telegram(message_id)

            return result

        except Exception as e:
            terminal_task.cancel()
            telegram_task.cancel()
            raise e

    async def _ask_tone_preference(self) -> dict:
        """Ask user which tone they prefer for regeneration."""
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("😊 More Casual", callback_data="casual"),
                InlineKeyboardButton("💼 More Formal", callback_data="formal"),
            ]
        ])

        message = await self.bot.send_message(
            chat_id=self.chat_id,
            text="🔄 How should I adjust the tone?",
            reply_markup=keyboard,
        )

        # Print terminal prompt
        print("\n" + "=" * 50)
        print("Choose tone (here OR in Telegram):")
        print("  1 = casual")
        print("  2 = formal")
        print("=" * 50)

        response = await self._wait_for_tone_dual_input(message.message_id)

        await self.bot.send_message(
            self.chat_id,
            f"🔄 Regenerating with {response} tone..."
        )

        return {"approved": False, "tone": response}

    async def _wait_for_tone_terminal(self) -> str:
        """Wait for tone choice from terminal."""
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, input, "Your choice (1/2): ")
        response = response.strip()
        if response == "1":
            return "casual"
        elif response == "2":
            return "formal"
        return None

    async def _wait_for_tone_dual_input(self, message_id: int) -> str:
        """Wait for tone input from either Telegram or terminal."""
        terminal_task = asyncio.create_task(self._wait_for_tone_terminal())
        telegram_task = asyncio.create_task(self._wait_for_telegram(message_id))

        done, pending = await asyncio.wait(
            [terminal_task, telegram_task],
            return_when=asyncio.FIRST_COMPLETED
        )

        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        result = done.pop().result()

        if result is None:
            print("Invalid input. Use '1' or '2'. Waiting for Telegram...")
            return await self._wait_for_telegram(message_id)

        return result

    async def notify_posted(self, url: str):
        """Notify user that post was published."""
        await self.bot.send_message(
            self.chat_id,
            f"🎉 Posted successfully!\n\n🔗 {url}"
        )


def create_approver() -> TelegramApprover:
    """Create a TelegramApprover using environment variables."""
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if not bot_token:
        raise ValueError("TELEGRAM_BOT_TOKEN environment variable is required")
    if not chat_id:
        raise ValueError("TELEGRAM_CHAT_ID environment variable is required")

    return TelegramApprover(bot_token, chat_id)


async def request_approval(post_text: str, image_data: bytes = None) -> dict:
    """Convenience function to request approval."""
    approver = create_approver()
    return await approver.send_for_approval(post_text, image_data)


async def notify_posted(url: str):
    """Convenience function to notify user of successful post."""
    approver = create_approver()
    await approver.notify_posted(url)
