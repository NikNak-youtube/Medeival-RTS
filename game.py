#!/usr/bin/env python3
"""
Medieval RTS Game
A real-time strategy game with single player (vs AI) and multiplayer support.

Run this file to start the game.
"""

from src.game import Game


def main():
    """Main entry point."""
    game = Game()
    game.run()


if __name__ == "__main__":
    main()
