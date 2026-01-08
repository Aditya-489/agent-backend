import logging
import gspread
from google.oauth2.service_account import Credentials  # CHANGED: New Auth Library
from dotenv import load_dotenv
from livekit import rtc
from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    JobProcess,
    cli,
    inference,
    room_io,
    function_tool,
    RunContext,
)
from livekit.plugins import noise_cancellation, silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("agent")

load_dotenv(".env.local")

# --- Configuration ---
GOOGLE_CREDENTIALS_FILE = "credentials.json"
SHEET_NAME = "Hotel booking"  # Ensure this matches your Google Sheet name exactly

class Assistant(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions="""ROLE:
    You are StayBot, a warm, friendly hotel receptionist at Grand Vista Hotel.
    VOICE STYLE:
    - Natural pacing
    - Short sentences
    - Occasional fillers like "Sure", "Alright", "Got it"
    - Never sound scripted
    - Smile while speaking

    CONVERSATION RULES:
    1. Always ask for PHONE NUMBER before confirming booking.
    2. Repeat key details once before confirmation.
    3. Never jump steps.

    BOOKING FLOW (MANDATORY):
    1. Greet
    2. Ask dates (Check-in and Check-out)
    3. Ask beds
    4. Quote price
    5. Ask name
    6. Ask phone number
    7. Repeat summary
    8. Confirm booking -> Call the "book_room" tool.
    9. Say goodbye naturally.

    BUSINESS RULES:
    - ₹1000 per bed per night
    - Max 2 beds
    - Breakfast free if stay > 1 night
    """
        )

    @function_tool
    async def book_room(
        self, 
        ctx: RunContext, 
        guest_name: str, 
        phone: str, 
        check_in: str, 
        check_out: str, 
        beds: int
    ):
        """
        Saves the confirmed booking details to the hotel's Google Sheet.
        
        Args:
            guest_name: The full name of the guest.
            phone: The guest's phone number.
            check_in: Check-in date (e.g., "tomorrow" or a specific date).
            check_out: Check-out date.
            beds: Number of beds requested.
        """
        logger.info(f"Attempting to book for {guest_name}")
        
        try:
            # --- CHANGED: Authenticate using google-auth ---
            scopes = [
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"
            ]
            
            creds = Credentials.from_service_account_file(
                GOOGLE_CREDENTIALS_FILE, scopes=scopes
            )
            client = gspread.authorize(creds)

            # Open the sheet and append row
            # Note: client.open opens the File, .sheet1 selects the first tab
            sheet = client.open(SHEET_NAME).sheet1
            sheet.append_row([guest_name, phone, check_in, check_out, beds])
            
            logger.info("Booking saved successfully.")
            return "Booking successfully saved to the system."
            
        except FileNotFoundError:
            logger.error("credentials.json file not found.")
            return "Error: System offline (Credential file missing)."
        except Exception as e:
            logger.error(f"Failed to save booking: {e}")
            return "An error occurred while saving the booking."


server = AgentServer()


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


server.setup_fnc = prewarm


@server.rtc_session()
async def my_agent(ctx: JobContext):
    # Logging setup
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }

    session = AgentSession(
        stt=inference.STT(model="assemblyai/universal-streaming", language="en"),
        llm=inference.LLM(model="openai/gpt-4.1-mini"),
        tts=inference.TTS(
            model="cartesia/sonic-3", voice="9626c31c-bec5-4cca-baa8-f8ba9e84c8bc"
        ),
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        preemptive_generation=True,
    )

    await session.start(
        agent=Assistant(),
        room=ctx.room,
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(
                noise_cancellation=lambda params: noise_cancellation.BVCTelephony()
                if params.participant.kind == rtc.ParticipantKind.PARTICIPANT_KIND_SIP
                else noise_cancellation.BVC(),
            ),
        ),
    )

    await ctx.connect()


if __name__ == "__main__":
    cli.run_app(server)