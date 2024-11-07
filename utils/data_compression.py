import zlib
import pickle
import numpy as np
import blosc
import pickle
import base64

def compare_data_structures(data1, data2):
    """
    Recursively compare two data structures that may contain nested dictionaries and numpy arrays.
    Returns True if they are the same, False otherwise.
    """
    if type(data1) != type(data2):
        return False

    if isinstance(data1, dict):
        if data1.keys() != data2.keys():
            return False
        for key in data1:
            if not compare_data_structures(data1[key], data2[key]):
                return False
    elif isinstance(data1, np.ndarray):
        if not np.array_equal(data1, data2):  # For exact match
            return False
    else:
        if data1 != data2:
            return False
    
    return True

def compress_data(data):
    """
    Compresses the data structure using zlib without any precision loss.
    """
    # Serialize the data with pickle
    serialized_data = pickle.dumps(data)
    # Compress the serialized data
    compressed_data = zlib.compress(serialized_data, level=9)  # level=9 for max compression
    return compressed_data

def decompress_data(compressed_data):
    """
    Decompresses the data structure using zlib.
    """
    # Decompress and deserialize
    serialized_data = zlib.decompress(compressed_data)
    data = pickle.loads(serialized_data)
    return data



def compress_data_blosc(data):
    """
    Compresses the data structure using blosc without any precision loss.
    """
    # Serialize the data
    serialized_data = pickle.dumps(data)
    # Compress the serialized data
    compressed_data = blosc.compress(serialized_data, typesize=8, clevel=9)  # typesize=8 for double precision
    return compressed_data

def decompress_data_blosc(compressed_data):
    """
    Decompresses the data structure using blosc.
    """
    # Decompress and deserialize
    serialized_data = blosc.decompress(compressed_data)
    data = pickle.loads(serialized_data)
    return data


def compress_and_encode_data(data):
    # Serialize and compress data
    serialized_data = pickle.dumps(data)
    compressed_data = blosc.compress(serialized_data, typesize=8, clevel=9)
    # Encode compressed bytes as a Base64 string
    encoded_data = base64.b64encode(compressed_data).decode('utf-8')
    return encoded_data

def decode_and_decompress_data(encoded_data):
    # Decode from Base64 to compressed bytes
    compressed_data = base64.b64decode(encoded_data.encode('utf-8'))
    # Decompress and deserialize the data
    serialized_data = blosc.decompress(compressed_data)
    data = pickle.loads(serialized_data)
    return data