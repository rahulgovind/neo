import pytest
import os
import tempfile
from src.utils.files import patch
from src.core.exceptions import FatalError

def test_patch_basic():
    """Test basic patch functionality"""
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        # Write test content
        tmp.write(b"line 1\nline 2\nline 3\nline 4\nline 5\n")
        tmp_path = tmp.name
    
    try:
        # Create a diff that replaces line 3 with a new line
        diff_text = "-3 line 3\n+3 new line 3"
        
        # Apply the patch
        result = patch(tmp_path, diff_text)
        
        # Expected result
        expected = "line 1\nline 2\nnew line 3\nline 4\nline 5\n"
        
        assert result == expected
    finally:
        # Clean up
        os.unlink(tmp_path)

def test_patch_add_lines():
    """Test adding lines with patch"""
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        # Write test content
        tmp.write(b"line 1\nline 2\nline 3\n")
        tmp_path = tmp.name
    
    try:
        # Create a diff that adds lines
        diff_text = " 2 line 2\n+3 new line after 2\n+3 another new line"
        
        # Apply the patch
        result = patch(tmp_path, diff_text)
        
        # Expected result
        expected = "line 1\nline 2\nnew line after 2\nanother new line\nline 3\n"
        
        assert result == expected
    finally:
        # Clean up
        os.unlink(tmp_path)

def test_patch_delete_lines():
    """Test deleting lines with patch"""
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        # Write test content
        tmp.write(b"line 1\nline 2\nto be deleted\nline 4\nline 5\n")
        tmp_path = tmp.name
    
    try:
        # Create a diff that deletes a line
        diff_text = "-3 to be deleted"
        
        # Apply the patch
        result = patch(tmp_path, diff_text)
        
        # Expected result
        expected = "line 1\nline 2\nline 4\nline 5\n"
        
        assert result == expected
    finally:
        # Clean up
        os.unlink(tmp_path)

def test_patch_mismatch_error():
    """Test patch fails when content doesn't match"""
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        # Write test content
        tmp.write(b"line 1\nline 2\nline 3\n")
        tmp_path = tmp.name
    
    try:
        # Create a diff with incorrect line content
        diff_text = "-2 wrong content"
        
        # Patch should raise FatalError
        with pytest.raises(FatalError):
            patch(tmp_path, diff_text)
    finally:
        # Clean up
        os.unlink(tmp_path)

def test_patch_invalid_format():
    """Test patch fails with invalid format"""
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        # Write test content
        tmp.write(b"line 1\nline 2\nline 3\n")
        tmp_path = tmp.name
    
    try:
        # Create a diff with invalid format
        diff_text = "x2 line 2"  # Invalid prefix
        
        # Patch should raise FatalError
        with pytest.raises(FatalError):
            patch(tmp_path, diff_text)
    finally:
        # Clean up
        os.unlink(tmp_path)

def test_patch_append_lines():
    """Test appending lines at the end of file"""
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        # Write test content
        tmp.write(b"line 1\nline 2\nline 3\n")
        tmp_path = tmp.name
    
    try:
        # Create a diff that adds a line at the end
        diff_text = "+4 new line at end"
        
        # Apply the patch
        result = patch(tmp_path, diff_text)
        
        # Expected result
        expected = "line 1\nline 2\nline 3\nnew line at end\n"
        
        assert result == expected
    finally:
        # Clean up
        os.unlink(tmp_path)

def test_patch_complex_changes():
    """Test complex changes with patch"""
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        # Write test content
        tmp.write(b"line 1\nline 2\nline 3\nline 4\nline 5\n")
        tmp_path = tmp.name
    
    try:
        # Create a complex diff with multiple operations
        diff_text = """-2 line 2
-4 line 4
+2 new line 2
+2 extra line
 5 line 5"""
        
        # Apply the patch
        result = patch(tmp_path, diff_text)
        
        # Expected result
        expected = "line 1\nnew line 2\nextra line\nline 3\nline 5\n"
        
        assert result == expected
    finally:
        # Clean up
        os.unlink(tmp_path)

def test_patch_empty_lines():
    """Test patch with multiple consecutive empty lines"""
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        # Write test content with multiple consecutive empty lines
        tmp.write(b"line 1\n\n\nline 4\nline 5\n")
        tmp_path = tmp.name
    
    try:
        # Create a diff that operates on empty lines and around them
        diff_text = " 1 line 1\n-2 \n+2 new line 2\n+3 new line 3\n 4 line 4"
        
        # Apply the patch
        result = patch(tmp_path, diff_text)
        
        # Expected result
        expected = "line 1\nnew line 2\nnew line 3\n\nline 4\nline 5\n"
        
        assert result == expected
    finally:
        # Clean up
        os.unlink(tmp_path)

def test_patch_empty_file():
    """Test appending to an empty file"""
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        # Create an empty file
        tmp.write(b"")
        tmp_path = tmp.name
    
    try:
        # Create a diff that adds content to an empty file
        diff_text = "+1 first line\n+1 second line"
        
        # Apply the patch
        result = patch(tmp_path, diff_text)
        
        # Expected result
        expected = "first line\nsecond line"
        
        assert result == expected
    finally:
        # Clean up
        os.unlink(tmp_path)

def test_patch_with_empty_line_content():
    """Test patching with empty line content in the diff"""
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        # Write test content with text and blank lines
        content = "Header\n\nThe Agent builds on top of the Model:\n\n- Feature 1\n- Feature 2\n"
        tmp.write(content.encode('utf-8'))
        tmp_path = tmp.name
    
    try:
        # Create a diff that has empty line content (line 2 is blank)
        # The +101 notation with nothing after it represents adding an empty line
        diff_text = "-2 \n+2\n-3 The Agent builds on top of the Model:\n+3 The Agent builds on top of the Shell:\n"
        
        # Apply the patch
        result = patch(tmp_path, diff_text)
        
        # Expected result - should correctly handle both empty lines
        expected = "Header\n\nThe Agent builds on top of the Shell:\n\n- Feature 1\n- Feature 2\n"
        
        assert result == expected
    finally:
        # Clean up
        os.unlink(tmp_path)
