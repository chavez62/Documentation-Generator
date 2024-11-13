import openai
from typing import Dict, List, Optional, Tuple, Any
from dotenv import load_dotenv
import os
import json
import datetime
from pathlib import Path
from tqdm import tqdm
import time
from colorama import init, Fore, Style
import argparse
import sys

# Initialize colorama for Windows color support
init()


def load_config():
    """Load environment variables from .env file."""
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not found in environment variables")
    return api_key


def validate_code_input(code: str) -> Tuple[bool, str]:
    """Validate the code input."""
    if not code.strip():
        return False, "Code input cannot be empty"
    return True, ""


def validate_language(language: str) -> Tuple[bool, str]:
    """Validate the programming language input."""
    valid_languages = {'python', 'javascript', 'java',
                       'cpp', 'c++', 'typescript', 'ruby', 'go', 'rust'}
    if not language.lower() in valid_languages:
        return False, f"Unsupported language. Supported languages: {', '.join(valid_languages)}"
    return True, ""


def validate_style(style: str) -> Tuple[bool, str]:
    """Validate the docstring style input."""
    valid_styles = {'google', 'numpy', 'sphinx'}
    if not style.lower() in valid_styles:
        return False, f"Unsupported style. Supported styles: {', '.join(valid_styles)}"
    return True, ""


def load_code_from_file(file_path: str) -> str:
    """Load code from a file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        raise ValueError(f"Error reading file: {str(e)}")


def save_documentation(docs: Dict, docstring: str, code: str, output_format: str = 'txt') -> str:
    """Save the documentation to a file."""
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path("generated_docs")
    output_dir.mkdir(exist_ok=True)

    if output_format == 'json':
        output_file = output_dir / f"documentation_{timestamp}.json"
        output_data = {
            "documentation": docs,
            "docstring": docstring,
            "original_code": code
        }
        with open(output_file, 'w') as f:
            json.dump(output_data, f, indent=2)
    else:  # txt format
        output_file = output_dir / f"documentation_{timestamp}.txt"
        with open(output_file, 'w') as f:
            f.write("=== Original Code ===\n\n")
            f.write(code)
            f.write("\n\n=== Documentation ===\n\n")
            f.write("Overview:\n")
            f.write(docs['overview'].strip())
            f.write("\n\nFunctions:\n")
            f.write(docs['functions'].strip())
            f.write("\n\nParameters:\n")
            f.write(docs['parameters'].strip())
            f.write("\n\nExamples:\n")
            f.write(docs['examples'].strip())
            f.write("\n\nImprovements:\n")
            if isinstance(docs['improvements'], list):
                for improvement in docs['improvements']:
                    f.write(f"- {improvement}\n")
            else:
                f.write(docs['improvements'].strip())
            f.write("\n\n=== Generated Docstring ===\n\n")
            f.write(docstring)

    return str(output_file)


def get_multiline_input_windows() -> str:
    """Get multiline input with better Windows support."""
    print(f"{Fore.CYAN}Enter/Paste your code below (press Enter, then type 'done' to finish):{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}-------------------- Begin Code --------------------{Style.RESET_ALL}")

    lines = []
    while True:
        try:
            line = input()
            if line.strip().lower() == 'done':
                break
            lines.append(line)
        except EOFError:
            break
        except KeyboardInterrupt:
            raise KeyboardInterrupt("Input cancelled by user")

    print(f"{Fore.YELLOW}-------------------- End Code --------------------{Style.RESET_ALL}")
    return '\n'.join(lines)


def show_progress(description: str, seconds: int = 2):
    """Show a progress bar."""
    with tqdm(total=100, desc=description, bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt}') as pbar:
        for i in range(100):
            time.sleep(seconds/100)
            pbar.update(1)


def clear_screen():
    """Clear the terminal screen."""
    os.system('cls' if os.name == 'nt' else 'clear')


class ConversationHistory:
    def __init__(self):
        self.history = []
        self.output_dir = Path("documentation_history")
        self.output_dir.mkdir(exist_ok=True)

    def add_entry(self, code: str, docs: Dict[str, Any], docstring: str):
        """Add an entry to the conversation history."""
        entry = {
            'timestamp': datetime.datetime.now().isoformat(),
            'code': code,
            'documentation': docs,
            'docstring': docstring
        }
        self.history.append(entry)
        self._save_history()

    def _save_history(self):
        """Save conversation history to file."""
        history_file = self.output_dir / 'documentation_history.json'
        with open(history_file, 'w') as f:
            json.dump(self.history, f, indent=2)

    def show_history(self):
        """Display conversation history."""
        if not self.history:
            print(f"{Fore.YELLOW}No documentation history found.{Style.RESET_ALL}")
            return

        print(f"\n{Fore.CYAN}Documentation History:{Style.RESET_ALL}")
        for i, entry in enumerate(self.history, 1):
            print(
                f"\n{Fore.GREEN}Entry {i} - {entry['timestamp']}{Style.RESET_ALL}")
            print(f"Code length: {len(entry['code'])} characters")
            if 'error' not in entry['documentation']:
                print(
                    "Documentation sections: Overview, Functions, Parameters, Examples, Improvements")


class CodeDocumentationGenerator:
    def __init__(self, api_key: str):
        """Initialize the documentation generator with OpenAI API key."""
        openai.api_key = api_key

    def generate_documentation(self, code: str, language: str = "python") -> Dict:
        """Generate comprehensive documentation for the provided code."""
        prompt = f"""Analyze this {language} code and provide the following:
        1. A brief overview of what the code does
        2. Detailed function documentation
        3. Parameters and return values
        4. Usage examples
        5. Any potential improvements or considerations
        
        Code to analyze:
        {code}"""

        try:
            response = openai.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are an expert programmer who specializes in writing clear, comprehensive code documentation."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7
            )

            documentation = self._parse_documentation(
                response.choices[0].message.content)
            return documentation

        except Exception as e:
            return {"error": f"Failed to generate documentation: {str(e)}"}

    def generate_docstring(self, code: str, style: str = "google") -> str:
        """Generate a docstring for a specific function."""
        styles = {
            "google": "using Google style docstrings",
            "numpy": "using NumPy style docstrings",
            "sphinx": "using Sphinx style docstrings"
        }

        prompt = f"""Write a comprehensive docstring for this function {styles.get(style, 'using standard docstrings')}:
        
        {code}"""

        try:
            response = openai.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are an expert at writing clear, comprehensive function docstrings."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            return f"Failed to generate docstring: {str(e)}"

    def _parse_documentation(self, raw_response: str) -> Dict:
        """Parse the raw API response into structured documentation."""
        sections = {
            "overview": "",
            "functions": "",
            "parameters": "",
            "examples": "",
            "improvements": ""
        }

        current_section = "overview"
        improvement_point = ""

        for line in raw_response.split('\n'):
            line = line.strip()
            if not line:
                continue

            if line.startswith('1. Brief Overview:'):
                current_section = "overview"
                continue
            elif line.startswith('2. Detailed Function Documentation:'):
                current_section = "functions"
                continue
            elif line.startswith('3. Parameters and Return Values:'):
                current_section = "parameters"
                continue
            elif line.startswith('4. Usage Examples:'):
                current_section = "examples"
                continue
            elif line.startswith('5. Any potential improvements') or line.startswith('Improvements:'):
                current_section = "improvements"
                continue
            elif line.startswith('-') and current_section == "improvements":
                if improvement_point:
                    sections["improvements"].append(improvement_point.strip())
                improvement_point = line[1:].strip()
                continue

            if current_section == "improvements":
                if improvement_point:
                    improvement_point += " " + line
            else:
                if current_section in sections:
                    if isinstance(sections[current_section], str):
                        if sections[current_section] and not sections[current_section].endswith('\n'):
                            sections[current_section] += '\n'
                        sections[current_section] += line

        # Add the last improvement point if there is one
        if improvement_point:
            sections["improvements"].append(improvement_point.strip())

        return sections


def main():
    try:
        # Load the API key from environment variables
        api_key = load_config()

        # Initialize the generator and history
        generator = CodeDocumentationGenerator(api_key)
        history = ConversationHistory()

        while True:
            clear_screen()
            print(f"{Fore.CYAN}=== Code Documentation Generator ==={Style.RESET_ALL}")
            print("1. Generate full documentation")
            print("2. Generate docstring only")
            print("3. View supported languages and styles")
            print("4. Save documentation to file")
            print("5. Load code from file")
            print("6. View documentation history")
            print("7. Exit")

            try:
                choice = input(
                    f"\n{Fore.GREEN}Enter your choice (1-7): {Style.RESET_ALL}").strip()

                if choice == "7":
                    print(f"{Fore.YELLOW}Exiting...{Style.RESET_ALL}")
                    break

                elif choice == "3":
                    print(
                        f"\n{Fore.CYAN}Supported Programming Languages:{Style.RESET_ALL}")
                    print(
                        "python, javascript, java, cpp, c++, typescript, ruby, go, rust")
                    print(
                        f"\n{Fore.CYAN}Supported Docstring Styles:{Style.RESET_ALL}")
                    print("google, numpy, sphinx")
                    input("\nPress Enter to continue...")
                    continue

                elif choice == "6":
                    history.show_history()
                    input("\nPress Enter to continue...")
                    continue

                elif choice in ["1", "2", "4", "5"]:
                    if choice == "5":
                        file_path = input(
                            f"\n{Fore.GREEN}Enter the path to your code file: {Style.RESET_ALL}")
                        try:
                            code_to_document = load_code_from_file(file_path)
                            print(
                                f"\n{Fore.CYAN}Code loaded successfully!{Style.RESET_ALL}")
                        except Exception as e:
                            print(
                                f"{Fore.RED}Error loading file: {str(e)}{Style.RESET_ALL}")
                            input("\nPress Enter to continue...")
                            continue
                    else:
                        code_to_document = get_multiline_input_windows()

                    show_progress("Processing input", 1)

                    is_valid, error_msg = validate_code_input(code_to_document)
                    if not is_valid:
                        print(
                            f"\n{Fore.RED}Error: {error_msg}{Style.RESET_ALL}")
                        input("\nPress Enter to continue...")
                        continue

                    if choice in ["1", "4"]:
                        while True:
                            language = input(
                                f"\n{Fore.GREEN}Enter programming language (default: python): {Style.RESET_ALL}").strip() or "python"
                            is_valid, error_msg = validate_language(language)
                            if is_valid:
                                break
                            print(
                                f"{Fore.RED}Error: {error_msg}{Style.RESET_ALL}")

                        print(
                            f"\n{Fore.CYAN}Generating documentation...{Style.RESET_ALL}")
                        show_progress("Generating documentation", 2)
                        docs = generator.generate_documentation(
                            code_to_document, language=language)

                        print(
                            f"\n{Fore.CYAN}Generating docstring...{Style.RESET_ALL}")
                        show_progress("Generating docstring", 1)
                        docstring = generator.generate_docstring(
                            code_to_document)

                        # Add to history
                        history.add_entry(code_to_document, docs, docstring)

                        if "error" in docs:
                            print(
                                f"{Fore.RED}Error generating documentation: {docs['error']}{Style.RESET_ALL}")
                        else:
                            print(
                                f"\n{Fore.CYAN}Documentation:{Style.RESET_ALL}")
                            print(
                                f"{Fore.GREEN}Overview:{Style.RESET_ALL}", docs["overview"])
                            print(
                                f"\n{Fore.GREEN}Functions:{Style.RESET_ALL}", docs["functions"])
                            print(
                                f"\n{Fore.GREEN}Parameters:{Style.RESET_ALL}", docs["parameters"])
                            print(
                                f"\n{Fore.GREEN}Examples:{Style.RESET_ALL}", docs["examples"])
                            print(
                                f"\n{Fore.GREEN}Improvements:{Style.RESET_ALL}")
                            for improvement in docs["improvements"]:
                                print(f"- {improvement}")

                            if choice == "4":
                                output_format = input(
                                    f"\n{Fore.GREEN}Choose output format (json/txt, default: txt): {Style.RESET_ALL}").strip().lower() or "txt"
                                if output_format not in ["json", "txt"]:
                                    output_format = "txt"

                                output_file = save_documentation(
                                    docs, docstring, code_to_document, output_format)
                                print(
                                    f"\n{Fore.CYAN}Documentation saved to: {output_file}{Style.RESET_ALL}")

                    elif choice == "2":
                        # Get and validate docstring style
                        while True:
                            style = input(
                                f"\n{Fore.GREEN}Enter docstring style (google/numpy/sphinx, default: google): {Style.RESET_ALL}").strip() or "google"
                            is_valid, error_msg = validate_style(style)
                            if is_valid:
                                break
                            print(
                                f"{Fore.RED}Error: {error_msg}{Style.RESET_ALL}")

                        print(
                            f"\n{Fore.CYAN}Generating docstring...{Style.RESET_ALL}")
                        show_progress("Generating docstring", 1)
                        docstring = generator.generate_docstring(
                            code_to_document, style=style)

                        if docstring.startswith("Failed to generate"):
                            print(
                                f"{Fore.RED}Error generating docstring: {docstring}{Style.RESET_ALL}")
                        else:
                            print(
                                f"\n{Fore.CYAN}Generated Docstring:{Style.RESET_ALL}")
                            print(docstring)

                input("\nPress Enter to continue...")

            except KeyboardInterrupt:
                print(
                    f"\n{Fore.YELLOW}Operation cancelled by user.{Style.RESET_ALL}")
                input("\nPress Enter to continue...")
                continue

    except Exception as e:
        print(f"{Fore.RED}An error occurred: {str(e)}{Style.RESET_ALL}")
        input("\nPress Enter to exit...")


if __name__ == "__main__":
    # Add command line argument support
    parser = argparse.ArgumentParser(
        description='Code Documentation Generator')
    parser.add_argument('--file', type=str, help='Path to code file')
    parser.add_argument('--language', type=str,
                        default='python', help='Programming language')
    args = parser.parse_args()

    if args.file:
        try:
            api_key = load_config()
            generator = CodeDocumentationGenerator(api_key)
            code = load_code_from_file(args.file)
            docs = generator.generate_documentation(code, args.language)
            docstring = generator.generate_docstring(code)

            # Save results
            # Fixed: using 'code' instead of undefined 'code_to_document'
            output_file = save_documentation(docs, docstring, code, 'txt')
            print(f"Documentation saved to: {output_file}")
            sys.exit(0)
        except Exception as e:
            print(f"Error: {str(e)}")
            sys.exit(1)
    else:
        main()
