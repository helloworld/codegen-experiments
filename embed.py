import os
import re
import openai
import ast
import typescript


def chunk_directory(directory, max_chunk_size=1000, embedding_dim=100):
    files = []
    for root, _, filenames in os.walk(directory):
        for filename in filenames:
            if not (filename.endswith(".ts") or filename.endswith(".py")):
                continue
            if re.search(r"\/(\.[^\/]*)?$", root):
                continue
            if not is_file_in_gitignore(os.path.join(root, filename)):
                files.append(os.path.join(root, filename))
    embeddings = []
    for file in files:
        if file.endswith(".ts"):
            embeddings.extend(
                chunk_typescript_file(file, max_chunk_size, embedding_dim)
            )
        elif file.endswith(".py"):
            embeddings.extend(chunk_python_file(file, max_chunk_size, embedding_dim))
    return embeddings


def chunk_typescript_file(file_path, max_chunk_size=1000, embedding_dim=100):
    with open(file_path, "r") as f:
        code = f.read()
        source_file = typescript.create_source_file(
            file_path, code, typescript.ScriptTarget.ESNext
        )
        functions = []
        for node in source_file.statements:
            if isinstance(node, typescript.FunctionDeclaration):
                functions.append(node)
        function_chunks = []
        for function in functions:
            function_code = code[function.pos : function.end]
            # if the function is too long, chunk it by if statements, for loops, and while loops
            if len(function_code) > max_chunk_size:
                if_chunks = re.findall(
                    r"if .*?:[\s]+.*?(?=if|for|while|$)", function_code, re.DOTALL
                )
                for if_chunk in if_chunks:
                    function_chunks.append(if_chunk)
                for_chunks = re.findall(
                    r"for .*?:[\s]+.*?(?=if|for|while|$)", function_code, re.DOTALL
                )
                for for_chunk in for_chunks:
                    function_chunks.append(for_chunk)
                while_chunks = re.findall(
                    r"while .*?:[\s]+.*?(?=if|for|while|$)", function_code, re.DOTALL
                )
                for while_chunk in while_chunks:
                    function_chunks.append(while_chunk)
            else:
                function_chunks.append(function_code)
        # generate embeddings for each chunk
        embeddings = []
        for chunk in function_chunks:
            response = openai.Embedding.create(
                input=chunk, model="text-embedding-ada-002", n=embedding_dim
            )
            embeddings.append(response["data"][0]["embedding"])
        return embeddings


def chunk_python_file(file_path, max_chunk_size=1000, embedding_dim=100):
    with open(file_path, "r") as f:
        code = f.read()
        root = ast.parse(code)
        functions = [node for node in root.body if isinstance(node, ast.FunctionDef)]
        function_chunks = []
        for function in functions:
            function_code = code[
                function.body[0].lineno - 1 : function.body[-1].end_lineno
            ]
            # if the function is too long, chunk it by if statements, for loops, and while loops
            if len(function_code) > max_chunk_size:
                if_chunks = re.findall(
                    r"if .*?:[\s]+.*?(?=if|for|while|^\s*\w|$)",
                    function_code,
                    re.DOTALL | re.MULTILINE,
                )
                for if_chunk in if_chunks:
                    function_chunks.append(if_chunk)
                for_chunks = re.findall(
                    r"for .*?:[\s]+.*?(?=if|for|while|^\s*\w|$)",
                    function_code,
                    re.DOTALL | re.MULTILINE,
                )
                for for_chunk in for_chunks:
                    function_chunks.append(for_chunk)
                while_chunks = re.findall(
                    r"while .*?:[\s]+.*?(?=if|for|while|^\s*\w|$)",
                    function_code,
                    re.DOTALL | re.MULTILINE,
                )
                for while_chunk in while_chunks:
                    function_chunks.append(while_chunk)
                other_chunks = re.findall(
                    r"^(?:(?!if|for|while).*?:[\s]+.*?)(?=if|for|while|^\s*\w|$)",
                    function_code,
                    re.DOTALL | re.MULTILINE,
                )
                for other_chunk in other_chunks:
                    function_chunks.append(other_chunk)
            else:
                function_chunks.append(function_code)
        # generate embeddings for each chunk
        embeddings = []
        for chunk in function_chunks:
            response = openai.Embedding.create(
                input=chunk, model="text-embedding-ada-002", n=embedding_dim
            )
            embeddings.append(response["data"][0]["embedding"])
        return embeddings


def is_file_in_gitignore(file_path):
    with open(".gitignore", "r") as f:
        gitignore = f.read().splitlines()
        for pattern in gitignore:
            if pattern.startswith("#") or pattern == "":
                continue
            if pattern.startswith("!"):
                pattern = pattern[1:]
                if not re.match(pattern, file_path):
                    continue
            else:
                if re.match(pattern, file_path):
                    continue
            return True
    return False
