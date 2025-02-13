import glob
import openai
import os
import requests
import uuid
from flask import Flask, request, jsonify, send_file, render_template
from dotenv import load_dotenv
# Load environment variables from .env file
load_dotenv()

# Get OpenAI API key from environment variable
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Get ElevenLabs API key from environment variable
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
openai.api_key = OPENAI_API_KEY

ELEVENLABS_VOICE_STABILITY = 0.30
ELEVENLABS_VOICE_SIMILARITY = 0.75

# Choose your favorite ElevenLabs voice
ELEVENLABS_VOICE_NAME = "Raj"
ELEVENLABS_ALL_VOICES = []

app = Flask(__name__)

def get_voices() -> list:
    """Fetch the list of available ElevenLabs voices.
    :returns: A list of voice JSON dictionaries.
    :rtype: list
    """
    url = "https://api.elevenlabs.io/v1/voices"
    headers = {
        "xi-api-key": ELEVENLABS_API_KEY
    }
    response = requests.get(url, headers=headers)
    return response.json()["voices"]


def transcribe_audio(filename: str) -> str:
    """Transcribe audio to text.
    :param filename: The path to an audio file.
    :returns: The transcribed text of the file.
    :rtype: str
    """
    with open(filename, "rb") as audio_file:
        transcript = openai.Audio.transcribe("whisper-1", audio_file)
    return transcript.text


def limit_conversation_history(conversation: list, limit: int = 20) -> list:
    """Limit the size of conversation history.

    :param conversation: A list of previous user and assistant messages.
    :param limit: Number of latest messages to retain. Default is 3.
    :returns: The limited conversation history.
    :rtype: list
    """
    return conversation[-limit:]

def generate_reply(conversation: list) -> str:
    """Generate a ChatGPT response.
    :param conversation: A list of previous user and assistant messages.
    :returns: The ChatGPT response.
    :rtype: str
    """
    print("Original conversation length:", len(conversation))
    print("Original Conversation", conversation)
    # Limit conversation history
    conversation = limit_conversation_history(conversation)
    
    print("Limited conversation length:", len(conversation))
    print("New Conversation", conversation)
    
    response = openai.ChatCompletion.create(
      model="gpt-3.5-turbo",
      messages=[
            # {"role": "system", "content": "You are a Hindi tutor whose role is to help a kid learn Hindi. Your objective is to engage the kid in a conversation that helps him or her learn Hindi. You can do this by asking questions like what is a house called in Hindi? and see if the child responds correctly. If they do you congratulate and encourage them, if they do not tell the correct answer and be encouraging regardless. Help the kid in coming up with correct pronunciations and come up with any other new ways to help the kid learn Hindi. Continue to engage the kid in a conversation and help him learn new words in Hindi in this manner."},
            {"role": "system", "content": "Your role is a pirate character called Jollybeard from a story book. Your objective is to be an entertaining companion to a 6 year old kid. You should respond to messages in a funny manner and your responses should include a lot of pirate slang such as matey, rrrrrrs, arrrrggghhh etc. Your responses should be short and witty and not exceed more than one or two sentences each time."},
        ] + conversation,
        temperature=1
    )
    return response["choices"][0]["message"]["content"]



def generate_audio(text: str, output_path: str = "") -> str:
    """Converts
    :param text: The text to convert to audio.
    :type text : str
    :param output_path: The location to save the finished mp3 file.
    :type output_path: str
    :returns: The output path for the successfully saved file.
    :rtype: str
    """
    voices = ELEVENLABS_ALL_VOICES
    try:
        voice_id = next(filter(lambda v: v["name"] == ELEVENLABS_VOICE_NAME, voices))["voice_id"]
    except StopIteration:
        voice_id = voices[0]["voice_id"]
        voice_id = "jIBWwhRngkm8so6GFCYC"
        # voice_id = "wW6Wydk4CWSgIsxSzHGq"

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    headers = {
        "xi-api-key": ELEVENLABS_API_KEY,
        "content-type": "application/json"
    }
    data = {
        "text": text,
        "voice_settings": {
            "stability": ELEVENLABS_VOICE_STABILITY,
            "similarity_boost": ELEVENLABS_VOICE_SIMILARITY,
        }
    }
    response = requests.post(url, json=data, headers=headers)
    with open(output_path, "wb") as output:
        output.write(response.content)
    return output_path


@app.route('/')
def index():
    """Render the index page."""
    return render_template('index.html', voice=ELEVENLABS_VOICE_NAME)


@app.route('/transcribe', methods=['POST'])
def transcribe():
    """Transcribe the given audio to text using Whisper."""
    if 'file' not in request.files:
        return 'No file found', 400
    file = request.files['file']
    recording_file = f"{uuid.uuid4()}.wav"
    recording_path = f"uploads/{recording_file}"
    os.makedirs(os.path.dirname(recording_path), exist_ok=True)
    file.save(recording_path)
    transcription = transcribe_audio(recording_path)
        # Delete the .wav file after it is transcribed
    try:
        os.remove(recording_path)
    except OSError as e:
        print(f"Error: {recording_path} : {e.strerror}")
    return jsonify({'text': transcription})

def clean_output_dir(directory: str):
    """Deletes all .mp3 files from a given directory.
    :param directory: The directory path to clean.
    """
    files = glob.glob(f'{directory}/*.mp3')
    for file in files:
        try:
            os.remove(file)
        except OSError as e:
            print(f"Error: {file} : {e.strerror}")

@app.route('/conversation', methods=['POST'])
def conversation():
    """Generate a response from the given audio, then convert it to audio using ElevenLabs."""
    if 'file' not in request.files:
        return 'No file found', 400
    file = request.files['file']
    recording_file = f"{uuid.uuid4()}.wav"
    recording_path = f"uploads/{recording_file}"
    os.makedirs(os.path.dirname(recording_path), exist_ok=True)
    file.save(recording_path)
    # Transcribe the audio to text
    transcription = transcribe_audio(recording_path)
    # Delete the .wav file after it is transcribed
    try:
        os.remove(recording_path)
    except OSError as e:
        print(f"Error: {recording_path} : {e.strerror}")
        
    # Generate a response from the transcription
    conversation = [
        {"role": "user", "content": transcription}
    ]
    reply = generate_reply(conversation)

    # Convert the response to audio
    reply_file = f"{uuid.uuid4()}.mp3"
    reply_path = f"outputs/{reply_file}"
    os.makedirs(os.path.dirname(reply_path), exist_ok=True)
    generate_audio(reply, output_path=reply_path)

    return jsonify({'text': reply, 'audio': f"/listen/{reply_file}"})


@app.route('/ask', methods=['POST'])
def ask():
    # Clean the outputs directory before generating a new response
    clean_output_dir("outputs")
    
    """Generate a ChatGPT response from the given conversation, then convert it to audio using ElevenLabs."""
    conversation = request.get_json(force=True).get("conversation", "")
    reply = generate_reply(conversation)
    reply_file = f"{uuid.uuid4()}.mp3"
    reply_path = f"outputs/{reply_file}"
    os.makedirs(os.path.dirname(reply_path), exist_ok=True)
    generate_audio(reply, output_path=reply_path)


    return jsonify({'text': reply, 'audio': f"/listen/{reply_file}"})


@app.route('/listen/<filename>')
def listen(filename):
    """Return the audio file located at the given filename."""
    return send_file(f"outputs/{filename}", mimetype="audio/mp3", as_attachment=False)


if ELEVENLABS_API_KEY:
    if not ELEVENLABS_ALL_VOICES:
        ELEVENLABS_ALL_VOICES = get_voices()
    if not ELEVENLABS_VOICE_NAME:
        ELEVENLABS_VOICE_NAME = ELEVENLABS_ALL_VOICES[0]["name"]

if __name__ == '__main__':
    app.run()
