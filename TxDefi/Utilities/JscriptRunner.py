import json
import subprocess

def execute_js_file(js_file_path: str, args: list)->dict[str,str]:
    # Example usage
    #subprocess.run(["cmd", "/c", "dir"])
    """
    Execute a JavaScript file with the specified arguments.

    :param ts_file_path: Path to the TypeScript file.
    :param args: List of arguments to pass to the TypeScript file.
    """
    try:
        # Construct the command
        command = ["node", js_file_path] + args

        # Run the command
        result = subprocess.run(
            command,
            text=True,              # Ensures the output is a string
            stdout=subprocess.PIPE, # Captures standard output
            stderr=subprocess.PIPE  # Captures standard error
        )

        # Print the result
        if result.returncode == 0:
            # Split the input string into lines
            lines = result.stdout.strip().split("\n")

            # Extract the last line
            last_line = lines[-1].strip()

            try:
                # Parse the last line as JSON
                parsed_json = json.loads(last_line)
                return parsed_json
            except json.JSONDecodeError as e:
                print("Error parsing JSON:", e)
            print("Output:", result.stdout)
        else:
            print("Error:", result.stderr)
    except FileNotFoundError as e:
        print("Error: Make sure node is installed and accessible in your PATH.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
