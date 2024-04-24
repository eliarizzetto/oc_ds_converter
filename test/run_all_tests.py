from subprocess import Popen

def main():
    Popen(
        ['poetry', 'run', 'python', '-m', 'unittest', 'discover', '-s', 'test', '-p', '*.py', '-b']
    )