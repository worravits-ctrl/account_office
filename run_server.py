import sys
import logging
import traceback
from app import app

if __name__ == '__main__':
    try:
        # Set up detailed logging
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s [%(levelname)s] %(message)s'
        )
        logger = logging.getLogger(__name__)
        
        print("-" * 50)
        print("Starting Flask server...")
        print("Python version:", sys.version)
        print("Attempting to bind to: http://127.0.0.1:3000")
        print("-" * 50)
        
        # Run without reloader/debugger
        app.run(
            host='127.0.0.1', 
            port=3000,
            debug=False,
            use_reloader=False
        )
    except Exception as e:
        print("\nERROR: Failed to start server!")
        print("Exception:", str(e))
        print("\nFull traceback:")
        traceback.print_exc()
        print("\nPlease check if:")
        print("1. Port 3000 is not in use")
        print("2. You have permission to bind to the port")
        print("3. Your firewall allows the connection")
        sys.exit(1)
