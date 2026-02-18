"""
Example usage of YouTube API Core

This module demonstrates how to use the YouTubeAPI class for various operations.
"""

import logging
from backend.services.youtube_api import YouTubeAPI, initialize_youtube_api

# Configure logging for your application
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


def example_basic_usage():
    """Basic usage with context manager (recommended)."""
    print("=== Basic Usage Example ===\n")

    try:
        # Use context manager for automatic cleanup
        with YouTubeAPI() as youtube:
            if youtube.is_connected():
                # Get live chat ID from active broadcast
                live_chat_id = youtube.client.get_active_live_chat_id()

                if live_chat_id:
                    # Send a message
                    success = youtube.client.send_message(
                        live_chat_id,
                        "¡Hola desde PowerBot!"
                    )
                    if success:
                        print("✓ Message sent successfully")
                    else:
                        print("✗ Failed to send message")

    except ValueError as e:
        print(f"Configuration error: {e}")
    except Exception as e:
        print(f"Error: {e}")


def example_singleton_pattern():
    """Using singleton pattern for global access."""
    print("\n=== Singleton Pattern Example ===\n")

    try:
        # Initialize once
        api = initialize_youtube_api()

        if api.is_connected():
            # Get the same instance later
            from backend.services.youtube_api import get_youtube_api
            youtube = get_youtube_api()

            if youtube and youtube.client:
                live_chat_id = youtube.client.get_active_live_chat_id()
                if live_chat_id:
                    print(f"Live Chat ID: {live_chat_id}")

    except Exception as e:
        print(f"Error: {e}")


def example_manual_management():
    """Manual connection management."""
    print("\n=== Manual Management Example ===\n")

    try:
        # Create instance
        youtube = YouTubeAPI()

        # Connect explicitly
        if youtube.connect():
            print("✓ Connected to YouTube API")

            if youtube.client:
                # Your operations here
                live_chat_id = youtube.client.get_active_live_chat_id()

            # Disconnect when done
            youtube.disconnect()
            print("✓ Disconnected from YouTube API")

    except Exception as e:
        print(f"Error: {e}")


def example_custom_keys_dir():
    """Using custom keys directory."""
    print("\n=== Custom Keys Directory Example ===\n")

    try:
        # Specify custom keys directory
        custom_keys = "/path/to/custom/keys"
        youtube = YouTubeAPI(keys_dir=custom_keys)

        if youtube.connect():
            # Your operations here
            pass

    except ValueError as e:
        print(f"Configuration error: {e}")


if __name__ == "__main__":
    # Run examples
    example_basic_usage()
    example_singleton_pattern()
    example_manual_management()
