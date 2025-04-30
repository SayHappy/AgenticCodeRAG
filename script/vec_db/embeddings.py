import numpy as np
from typing import List, Dict, Any, Optional, Union
import re

class EmbeddingGenerator:
    """Handles embedding generation for code blocks"""
    
    def __init__(self, model_name: str = "bge-m3", cache_dir: Optional[str] = None):
        """
        Initialize the embedding generator
        
        Args:
            model_name: The model to use for embeddings
            cache_dir: Optional directory to cache model files
        """
        self.model_name = model_name
        self.cache_dir = cache_dir
        self.model = None
        self.tokenizer = None
        self.device = None
        self._load_model()
    
    def _load_model(self):
        """Load the embedding model"""
        try:
            from sentence_transformers import SentenceTransformer
            import torch
            
            # Determine device (CUDA/MPS/CPU)
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
            if self.device == "cpu" and hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                self.device = "mps"  # Use MPS on Mac if available
                
            # Load model with appropriate parameters
            model_kwargs = {"device": self.device}
            if self.cache_dir:
                model_kwargs["cache_folder"] = self.cache_dir
            self.model = SentenceTransformer(self.model_name, **model_kwargs)
            print(f"Loaded embedding model '{self.model_name}' on {self.device}")
            
        except ImportError:
            print("Warning: sentence-transformers not installed. Using fallback embedding.")
            self.model = None
    
    def _prepare_code_for_embedding(self, code: str) -> str:
        """
        Prepare code for embedding by cleaning it and adding context
        
        Returns cleaned code with normalized whitespace
        """
        # Remove excessive blank lines 
        code = re.sub(r'\n\s*\n\s*\n+', '\n\n', code)
        
        # Normalize indentation
        lines = code.split('\n')
        min_indent = float('inf')
        
        for line in lines:
            if line.strip():  # Skip empty lines
                indent = len(line) - len(line.lstrip())
                min_indent = min(min_indent, indent) if indent > 0 else min_indent
        
        if min_indent < float('inf'):
            normalized_lines = []
            for line in lines:
                if line.strip():  # Only process non-empty lines
                    if len(line) > min_indent:
                        normalized_lines.append(line[min_indent:])
                    else:
                        normalized_lines.append(line)
                else:
                    normalized_lines.append('')
                    
            code = '\n'.join(normalized_lines)
        
        return code
    
    def _fallback_embedding(self, text: str) -> List[float]:
        """
        Generate a simple fallback embedding when no model is available
        This is NOT for production use, only for testing/development
        """
        import hashlib
        
        # Use a hash function to generate a deterministic vector
        hash_obj = hashlib.md5(text.encode('utf-8'))
        hash_bytes = hash_obj.digest()
        
        # Convert hash bytes to floats between -1 and 1
        vec = []
        for i in range(0, min(1024, len(hash_bytes))):
            val = (hash_bytes[i % len(hash_bytes)] / 255.0) * 2 - 1
            vec.append(val)
            
        # Pad if necessary
        while len(vec) < 1024:
            vec.append(0.0)
            
        # Normalize
        norm = np.sqrt(sum(x*x for x in vec))
        return [x/norm for x in vec]
    
    def generate_embedding(self, code: str, metadata: Optional[Dict[str, Any]] = None) -> List[float]:
        """
        Generate an embedding for a code block
        
        Args:
            code: The source code to embed
            metadata: Optional metadata to enhance embedding context
            
        Returns:
            List[float]: The embedding vector
        """
        if not code or code.isspace():
            # Return zero vector for empty content
            return [0.0] * 1024
            
        # Clean and prepare code
        prepared_code = self._prepare_code_for_embedding(code)
        
        # Add metadata context if provided
        if metadata:
            context_prefix = ""
            
            if 'language' in metadata:
                context_prefix += f"Language: {metadata['language']}\n"
                
            if 'framework' in metadata:
                context_prefix += f"Framework: {metadata['framework']}\n"
                
            if 'element_type' in metadata:
                context_prefix += f"Type: {metadata['element_type']}\n"
                
            if 'name' in metadata:
                context_prefix += f"Name: {metadata['name']}\n"
                
            prepared_code = context_prefix + prepared_code
            
        # Generate embedding
        if self.model:
            # Use the loaded model
            embedding = self.model.encode(prepared_code, normalize_embeddings=True)
            return embedding.tolist()
        else:
            # Use fallback for testing
            return self._fallback_embedding(prepared_code)
            
    def batch_generate_embeddings(self, code_blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Generate embeddings for multiple code blocks
        
        Args:
            code_blocks: List of dictionaries with 'code' and optional 'metadata' keys
            
        Returns:
            List of the same dictionaries with 'embedding' added
        """
        texts = []
        for block in code_blocks:
            code = block['code']
            metadata = block.get('metadata', {})
            
            # Clean and prepare code
            prepared_code = self._prepare_code_for_embedding(code)
            
            # Add metadata context if provided
            if metadata:
                context_prefix = ""
                
                if 'language' in metadata:
                    context_prefix += f"Language: {metadata['language']}\n"
                    
                if 'framework' in metadata:
                    context_prefix += f"Framework: {metadata['framework']}\n"
                    
                if 'element_type' in metadata:
                    context_prefix += f"Type: {metadata['element_type']}\n"
                    
                if 'name' in metadata:
                    context_prefix += f"Name: {metadata['name']}\n"
                    
                prepared_code = context_prefix + prepared_code
                
            texts.append(prepared_code)
            
        # Generate embeddings in batch
        if self.model and texts:
            embeddings = self.model.encode(texts, normalize_embeddings=True)
            for i, block in enumerate(code_blocks):
                block['embedding'] = embeddings[i].tolist()
        else:
            # Fallback
            for block in code_blocks:
                block['embedding'] = self._fallback_embedding(block['code'])
                
        return code_blocks 