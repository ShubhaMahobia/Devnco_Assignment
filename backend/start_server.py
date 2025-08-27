#!/usr/bin/env python3
"""
Simple startup script for the RAG application backend
"""
import sys
import os

# Add the backend directory to Python path
backend_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, backend_dir)

if __name__ == "__main__":
    try:
        from src.main import main
        print("Starting RAG Application Backend...")
        print("\nPress Ctrl+C to stop the server\n")
        main()
    except ImportError as e:
        print(f"Import error: {e}")
        print("Please make sure all dependencies are installed:")
        print("pip install -r requirements.txt")
        sys.exit(1)
    except Exception as e:
        print(f"Error starting server: {e}")
        sys.exit(1)
