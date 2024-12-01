from solathon import Client, Transaction, PublicKey, Keypair
from solathon.core.instructions import transfer
import hashlib
import json
import os
import qrcode
from pyzbar.pyzbar import decode
from PIL import Image
import requests
import time

# Solana Configuration
SOLANA_URL = "https://api.devnet.solana.com"  # Solana devnet URL
WALLET_PATH = "/path/to/keypair.json"  # Path to your wallet
OFFLINE_VOTES_FILE = "offline_votes.json"  # Local storage for offline votes

# Utility: Save offline votes to file
def save_offline_vote(vote_data):
    if not os.path.exists(OFFLINE_VOTES_FILE):
        with open(OFFLINE_VOTES_FILE, "w") as f:
            json.dump([], f)

    with open(OFFLINE_VOTES_FILE, "r") as f:
        votes = json.load(f)

    votes.append(vote_data)

    with open(OFFLINE_VOTES_FILE, "w") as f:
        json.dump(votes, f)

    print("No internet connection. Vote saved offline!")

# Utility: Sync offline votes to Solana
def sync_offline_votes(client, sender):
    if not os.path.exists(OFFLINE_VOTES_FILE):
        print("No offline votes to sync.")
        return

    with open(OFFLINE_VOTES_FILE, "r") as f:
        votes = json.load(f)

    for vote in votes:
        try:
            submit_vote_to_blockchain(client, sender, vote["voter_id"], vote["voting_session_id"], vote["session_token"])
        except Exception as e:
            print(f"Failed to sync vote {vote}: {e}")

    # Clear offline votes after syncing
    with open(OFFLINE_VOTES_FILE, "w") as f:
        json.dump([], f)

    print("All offline votes synchronized!")

# Function to generate a QR Code
def generate_qr_code(voter_id, voting_session_id):
    session_token = hashlib.sha256(f"{voter_id}-{voting_session_id}".encode()).hexdigest()
    qr_data = {
        "voter_id": voter_id,
        "voting_session_id": voting_session_id,
        "session_token": session_token,
    }
    qr_json = json.dumps(qr_data)
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(qr_json)
    qr.make(fit=True)
    img = qr.make_image(fill="black", back_color="white")
    img.save("voter_qr_code.png")
    print("QR Code generated and saved as voter_qr_code.png")

# Function to scan and decode a QR Code
def scan_qr_code(image_path):
    qr_data = decode(Image.open(image_path))
    if not qr_data:
        print("No QR Code found!")
        return None
    decoded_data = qr_data[0].data.decode("utf-8")
    qr_json = json.loads(decoded_data)
    print("QR Code Data:", qr_json)
    return qr_json

# Function to check if the sender has sufficient funds for the transaction
def has_sufficient_funds(client, sender_public_key, amount_needed):
    balance = client.get_balance(sender_public_key)
    if balance < amount_needed:
        print(f"Insufficient funds. Current balance: {balance}, required: {amount_needed}")
        return False
    return True

# Function to submit vote to Solana blockchain using solathon
def submit_vote_to_blockchain(client, sender, voter_id, voting_session_id, session_token):
    # Example transfer (replace with your actual logic for vote submission)
    receiver = PublicKey("4kqk9exxYZfUzp8hM3aRgjF1T8uHh9hYPJ21uqNTbrVp")  # Replace with actual receiver's public key
    
    amount = 100  # Define amount to transfer (in lamports)

    # Skip the account initialization check on devnet
    # Check if the sender has enough funds for the transaction
    if not has_sufficient_funds(client, sender.public_key, amount):
        print("Insufficient funds for transaction. Skipping transaction.")
        return  # Skip the transaction if there are insufficient funds

    # Create the transfer instruction
    instruction = transfer(
        from_public_key=sender.public_key,
        to_public_key=receiver,
        lamports=amount
    )

    # Create the transaction
    transaction = Transaction(instructions=[instruction], signers=[sender])

    # Send the transaction
    try:
        result = client.send_transaction(transaction)
        print("Transaction response:", result)
    except Exception as e:
        print(f"Blockchain submission failed: {e}")
        raise e  # Raise the error so that the normal failure is logged

# Check for internet connection
def is_connected():
    try:
        # Check if we can reach the Solana devnet
        response = requests.get(SOLANA_URL, timeout=5)
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False

# Retry logic for RPC failures
def send_transaction_with_retry(client, transaction, retries=3, delay=5):
    for attempt in range(retries):
        try:
            result = client.send_transaction(transaction)
            return result
        except requests.exceptions.RequestException as e:
            print(f"RPC request failed (Attempt {attempt + 1}): {e}")
            if attempt < retries - 1:
                time.sleep(delay)
            else:
                raise Exception(f"Failed after {retries} attempts.")
        except Exception as e:
            raise e

# Main Script
if __name__ == "__main__":

    # Initialize Solana client and wallet
    client = Client(SOLANA_URL)

    # Generate or load the sender's wallet
    sender = Keypair.from_private_key("EZDK1F8JytZqbfwn2KbrSDdFRYnRAjBszXKx8nG6hnqC")  # Replace with actual private key

    # Generate the QR code
    voter_id = "voter123"
    voting_session_id = "session456"
    generate_qr_code(voter_id, voting_session_id)

    # Scan the QR code
    scanned_data = scan_qr_code("voter_qr_code.png")
    if scanned_data:
        print("\nScanned Data Verified:")
        print(f"Voter ID: {scanned_data['voter_id']}")
        print(f"Voting Session ID: {scanned_data['voting_session_id']}")
        print(f"Session Token: {scanned_data['session_token']}")

        # Submit the vote (replace with actual logic for voting)
        if is_connected():
            try:
                submit_vote_to_blockchain(client, sender, scanned_data["voter_id"], scanned_data["voting_session_id"], scanned_data["session_token"])
            except Exception as e:
                print(f"Blockchain submission failed: {e}")
                save_offline_vote(scanned_data)
        else:
            # Save the vote offline if no internet
            print("No internet connection. Saving vote offline.")
            save_offline_vote(scanned_data)

    # Sync offline votes if connected and previous votes exist
    if is_connected():
        print("\nPrevious request Reattempt:")
        print("-------------------------------------")
        sync_offline_votes(client, sender)