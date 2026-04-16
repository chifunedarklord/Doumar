#!/usr/bin/env python3
"""
Test script for bcrypt password hashing implementation
"""

try:
    import bcrypt
    from core.services import AuthService
    
    print("=== Testing bcrypt implementation ===")
    
    # Test 1: Password hashing
    test_password = "test123"
    print(f"Testing password: '{test_password}'")
    
    hashed = AuthService.hash_password(test_password)
    print(f"Generated hash: {hashed[:30]}...")
    print(f"Hash length: {len(hashed)} characters")
    
    # Test 2: Password verification - correct password
    is_valid = AuthService.verify_password(test_password, hashed)
    print(f"Correct password verification: {is_valid}")
    
    # Test 3: Password verification - wrong password
    is_invalid = AuthService.verify_password("wrong", hashed)
    print(f"Wrong password verification: {is_invalid}")
    
    # Test 4: Different passwords generate different hashes
    hashed2 = AuthService.hash_password(test_password)
    print(f"Second hash different: {hashed != hashed2}")
    
    # Test 5: Both hashes verify the same password
    is_valid2 = AuthService.verify_password(test_password, hashed2)
    print(f"Both hashes verify correctly: {is_valid and is_valid2}")
    
    print("\n=== bcrypt implementation: SUCCESS ===")
    
except ImportError as e:
    print(f"Import error: {e}")
    print("Please install bcrypt: pip install bcrypt")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
