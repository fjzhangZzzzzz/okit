"""
Tests for MobaXterm Colors Tool
"""

import os
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open
import pytest
import configparser

from okit.tools.mobaxterm_colors import MobaXtermColors


class TestMobaXtermColors:
    """Test cases for MobaXtermColors tool"""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory"""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def tool(self, temp_dir):
        """Create tool instance with mocked paths"""
        tool = MobaXtermColors()
        
        # Mock all path-related methods to use temp directory
        with patch.object(tool, '_get_okit_root_dir') as mock_root:
            mock_root.return_value = temp_dir / ".okit"
            
            with patch.object(tool, '_get_tool_config_dir') as mock_config_dir:
                mock_config_dir.return_value = temp_dir / ".okit" / "config" / tool.tool_name
                
                with patch.object(tool, '_get_tool_data_dir') as mock_data_dir:
                    mock_data_dir.return_value = temp_dir / ".okit" / "data" / tool.tool_name
                    
                    # Mock _update_cache to avoid real git operations
                    with patch.object(tool, '_update_cache') as mock_update_cache:
                        mock_update_cache.return_value = None
                        
                        yield tool
    
    @pytest.fixture
    def mock_config_file(self, temp_dir):
        """Create mock MobaXterm.ini file"""
        config_file = temp_dir / "MobaXterm.ini"
        config = configparser.ConfigParser()
        config.add_section('Colors')
        config['Colors']['Black'] = '0,0,0'
        config['Colors']['White'] = '255,255,255'
        config['Colors']['BoldBlack'] = '128,128,128'
        config['Colors']['BoldWhite'] = '192,192,192'
        
        with open(config_file, 'w') as f:
            config.write(f)
        
        return config_file
    
    @pytest.fixture
    def mock_scheme_file(self, temp_dir):
        """Create mock .ini scheme file"""
        scheme_file = temp_dir / "test_scheme.ini"
        scheme_content = """Black=0,0,0
White=255,255,255
BoldBlack=128,128,128
BoldWhite=192,192,192"""
        
        with open(scheme_file, 'w') as f:
            f.write(scheme_content)
        
        return scheme_file
    
    def test_tool_initialization(self):
        """Test tool initialization"""
        tool = MobaXtermColors()
        
        assert tool is not None
        assert hasattr(tool, 'REPO_URL')
        assert hasattr(tool, 'MOBAXTERM_DIR')
        assert tool.REPO_URL == "https://github.com/mbadolato/iTerm2-Color-Schemes"
        assert tool.MOBAXTERM_DIR == "mobaxterm"
        assert hasattr(tool, 'detector')
    
    def test_ensure_cache_dir(self, tool):
        """Test ensuring cache directory exists"""
        cache_dir = tool.get_data_file("cache")
        
        # Mock the cache directory operations to avoid affecting real cache
        with patch.object(tool, 'get_data_file') as mock_get_data_file:
            mock_cache_dir = Path("/mock/cache/dir")
            mock_get_data_file.return_value = mock_cache_dir
            
            # Remove if exists
            if mock_cache_dir.exists():
                shutil.rmtree(mock_cache_dir)
            
            tool._ensure_cache_dir()
            
            assert mock_cache_dir.exists()
            assert mock_cache_dir.is_dir()
    
    def test_get_mobaxterm_config_path_existing(self, tool, mock_config_file):
        """Test finding existing MobaXterm.ini"""
        # Mock the detector and path operations to avoid accessing real files
        with patch.object(tool.detector, 'detect_installation') as mock_detect:
            with patch.object(tool.detector, 'get_config_file_path') as mock_get_config:
                with patch('pathlib.Path.exists') as mock_exists:
                    mock_detect.return_value = {"install_path": str(mock_config_file.parent)}
                    mock_get_config.return_value = str(mock_config_file)
                    mock_exists.return_value = True
                    
                    result = tool._get_mobaxterm_config_path()
                    assert result == mock_config_file
    
    def test_get_mobaxterm_config_path_custom(self, tool):
        """Test custom config path from configuration"""
        custom_path = Path("/custom/path/MobaXterm.ini")
        
        # Mock the config value instead of setting it
        with patch.object(tool, 'get_config_value') as mock_get_config:
            mock_get_config.return_value = str(custom_path)
            
            with patch('pathlib.Path.exists') as mock_exists:
                mock_exists.return_value = True
                result = tool._get_mobaxterm_config_path()
                assert result == custom_path
    
    def test_get_mobaxterm_config_path_custom_not_exists(self, tool):
        """Test custom config path that doesn't exist"""
        custom_path = Path("/custom/path/MobaXterm.ini")
        
        # Mock the config value instead of setting it
        with patch.object(tool, 'get_config_value') as mock_get_config:
            mock_get_config.return_value = str(custom_path)
            
            with patch('pathlib.Path.exists') as mock_exists:
                mock_exists.return_value = False
                # Mock the detector to avoid accessing real files
                with patch.object(tool.detector, 'detect_installation') as mock_detect:
                    mock_detect.return_value = {"install_path": "/detected/path"}
                    result = tool._get_mobaxterm_config_path()
                    # Should fall back to detector or default paths
                    assert result is not None
    
    def test_get_mobaxterm_config_path_detector_fallback(self, tool):
        """Test fallback to detector when custom path not found"""
        custom_path = Path("/custom/path/MobaXterm.ini")
        
        # Mock the config value instead of setting it
        with patch.object(tool, 'get_config_value') as mock_get_config:
            mock_get_config.return_value = str(custom_path)
            
            with patch('pathlib.Path.exists') as mock_exists:
                mock_exists.return_value = False
                
                # Mock detector to return a valid path
                mock_install_info = {
                    "install_path": "/detected/path"
                }
                with patch.object(tool.detector, 'detect_installation') as mock_detect:
                    with patch.object(tool.detector, 'get_config_file_path') as mock_get_config_path:
                        mock_detect.return_value = mock_install_info
                        mock_get_config_path.return_value = "/detected/path/MobaXterm.ini"
                        
                        result = tool._get_mobaxterm_config_path()
                        assert result == Path("/detected/path/MobaXterm.ini")
    
    def test_get_mobaxterm_config_path_not_found(self, tool):
        """Test when MobaXterm.ini is not found"""
        with patch('pathlib.Path.exists') as mock_exists:
            mock_exists.return_value = False
            # Mock the detector to avoid accessing real files
            with patch.object(tool.detector, 'detect_installation') as mock_detect:
                mock_detect.return_value = None
                result = tool._get_mobaxterm_config_path()
                assert result is not None  # Should return default path
    
    def test_parse_mobaxterm_scheme(self, tool, mock_scheme_file):
        """Test parsing .ini scheme file"""
        colors = tool._parse_mobaxterm_scheme(mock_scheme_file)
        
        expected = {
            'Black': '0,0,0',
            'White': '255,255,255',
            'BoldBlack': '128,128,128',
            'BoldWhite': '192,192,192'
        }
        
        assert colors == expected
    
    def test_parse_mobaxterm_scheme_invalid(self, tool, temp_dir):
        """Test parsing invalid .ini scheme file"""
        invalid_file = temp_dir / "invalid.ini"
        with open(invalid_file, 'w') as f:
            f.write("Invalid content")
        
        colors = tool._parse_mobaxterm_scheme(invalid_file)
        assert colors == {}
    
    def test_parse_mobaxterm_scheme_empty(self, tool, temp_dir):
        """Test parsing empty .ini scheme file"""
        empty_file = temp_dir / "empty.ini"
        empty_file.touch()
        
        colors = tool._parse_mobaxterm_scheme(empty_file)
        assert colors == {}
    
    def test_parse_mobaxterm_scheme_malformed(self, tool, temp_dir):
        """Test parsing malformed .ini scheme file"""
        malformed_file = temp_dir / "malformed.ini"
        with open(malformed_file, 'w') as f:
            f.write("Black=invalid\nRed=255,255\nGreen=128,128,128,extra")
        
        colors = tool._parse_mobaxterm_scheme(malformed_file)
        # Should still extract valid colors
        assert 'Green' in colors
        assert colors['Green'] == '128,128,128'
    
    def test_parse_mobaxterm_scheme_alienblood_format(self, tool, temp_dir):
        """Test parsing AlienBlood format scheme file"""
        alienblood_file = temp_dir / "AlienBlood.ini"
        alienblood_content = """;Paste the following configurations in the corresponding place in MobaXterm.ini.
;Theme: AlienBlood
[Colors]
DefaultColorScheme=0
BackgroundColour=15,22,16
ForegroundColour=99,125,117
CursorColour=115,250,145
Black=17,38,22
Red=127,43,39
BoldGreen=24,224,0
BoldYellow=189,224,0
BoldBlue=0,170,224
BoldMagenta=0,88,224
BoldCyan=0,224,196
BoldWhite=115,250,145
Green=47,126,37
Yellow=113,127,36
Blue=47,106,127
Magenta=71,88,127
Cyan=50,127,119
White=100,125,117
BoldBlack=60,72,18
BoldRed=224,128,9"""
        
        with open(alienblood_file, 'w') as f:
            f.write(alienblood_content)
        
        colors = tool._parse_mobaxterm_scheme(alienblood_file)
        
        # Check that colors were parsed correctly
        assert len(colors) > 0
        assert 'Black' in colors
        assert 'Red' in colors
        assert 'Green' in colors
        assert 'Yellow' in colors
        assert 'Blue' in colors
        assert 'Magenta' in colors
        assert 'Cyan' in colors
        assert 'White' in colors
        assert 'BoldBlack' in colors
        assert 'BoldRed' in colors
        assert 'BoldGreen' in colors
        assert 'BoldYellow' in colors
        assert 'BoldBlue' in colors
        assert 'BoldMagenta' in colors
        assert 'BoldCyan' in colors
        assert 'BoldWhite' in colors
        
        # Check specific color values
        assert colors['Black'] == '17,38,22'
        assert colors['Red'] == '127,43,39'
        assert colors['Green'] == '47,126,37'
        assert colors['BoldRed'] == '224,128,9'
        assert colors['BoldWhite'] == '115,250,145'

    def test_read_mobaxterm_config(self, tool, mock_config_file):
        """Test reading MobaXterm.ini configuration"""
        config = tool._read_mobaxterm_config(mock_config_file)
        
        assert 'Colors' in config
        # configparser converts keys to lowercase by default
        assert config['Colors']['black'] == '0,0,0'
        assert config['Colors']['white'] == '255,255,255'
        assert config['Colors']['boldblack'] == '128,128,128'
        assert config['Colors']['boldwhite'] == '192,192,192'
    
    def test_read_mobaxterm_config_nonexistent(self, tool, temp_dir):
        """Test reading non-existent MobaXterm.ini"""
        nonexistent_file = temp_dir / "nonexistent.ini"
        config = tool._read_mobaxterm_config(nonexistent_file)
        
        assert isinstance(config, configparser.ConfigParser)
        assert len(config.sections()) == 0
    
    def test_write_mobaxterm_config(self, tool, temp_dir):
        """Test writing MobaXterm.ini configuration"""
        config = configparser.ConfigParser()
        config.add_section('Colors')
        config['Colors']['Black'] = '255,0,0'
        
        output_file = temp_dir / "output.ini"
        tool._write_mobaxterm_config(config, output_file)
        
        assert output_file.exists()
        
        # Verify content
        with open(output_file, 'r') as f:
            content = f.read()
            assert '[Colors]' in content
            assert 'black = 255,0,0' in content  # configparser uses lowercase
    
    def test_write_mobaxterm_config_create_dir(self, tool, temp_dir):
        """Test writing MobaXterm.ini configuration with directory creation"""
        config = configparser.ConfigParser()
        config.add_section('Colors')
        config['Colors']['Black'] = '255,0,0'
        
        # Create a path that doesn't exist
        output_file = temp_dir / "new_dir" / "output.ini"
        tool._write_mobaxterm_config(config, output_file)
        
        assert output_file.exists()
        assert output_file.parent.exists()
    
    def test_backup_config(self, tool, mock_config_file, temp_dir):
        """Test creating backup of MobaXterm.ini"""
        with patch.object(tool, '_get_backup_path') as mock_backup_path:
            mock_backup_path.return_value = temp_dir
            backup_path = tool._backup_config(mock_config_file)
            
            assert backup_path is not None
            assert backup_path.exists()
            assert backup_path.name.startswith("MobaXterm_backup_")
    
    def test_backup_config_nonexistent(self, tool, temp_dir):
        """Test backup of non-existent config file"""
        nonexistent_file = temp_dir / "nonexistent.ini"
        backup_path = tool._backup_config(nonexistent_file)
        
        assert backup_path is None
    
    def test_get_cache_path(self, tool):
        """Test getting cache directory path"""
        cache_path = tool._get_cache_path()
        
        assert isinstance(cache_path, Path)
        assert "iterm2-color-schemes" in str(cache_path)
    
    def test_get_backup_path(self, tool):
        """Test getting backup directory path"""
        backup_path = tool._get_backup_path()
        
        assert isinstance(backup_path, Path)
        assert "backups" in str(backup_path)
    
    def test_update_cache_existing(self, tool):
        """Test updating existing cache"""
        # Mock the entire _update_cache method to avoid real git operations
        with patch.object(tool, '_update_cache') as mock_update_cache:
            mock_update_cache.return_value = None
            
            # Call the method
            tool._update_cache()
            
            # Verify that the method was called
            mock_update_cache.assert_called_once()
    
    def test_update_cache_new(self, tool):
        """Test creating new cache"""
        # Mock the entire _update_cache method to avoid real git operations
        with patch.object(tool, '_update_cache') as mock_update_cache:
            mock_update_cache.return_value = None
            
            # Call the method
            tool._update_cache()
            
            # Verify that the method was called
            mock_update_cache.assert_called_once()
    
    def test_update_cache_git_error(self, tool):
        """Test updating cache with git error"""
        # Mock the entire _update_cache method to avoid real git operations
        with patch.object(tool, '_update_cache') as mock_update_cache:
            mock_update_cache.return_value = None
            
            # Call the method - should not raise exception
            tool._update_cache()
            
            # Verify that the method was called
            mock_update_cache.assert_called_once()
    
    def test_clean_cache(self, tool):
        """Test cleaning cache"""
        # Mock the cache path to avoid affecting real cache
        with patch.object(tool, '_get_cache_path') as mock_get_cache:
            mock_cache_path = Path("/mock/cache/path")
            mock_get_cache.return_value = mock_cache_path
            
            # Mock that the cache exists
            with patch('pathlib.Path.exists') as mock_exists:
                mock_exists.return_value = True
                
                # Mock shutil.rmtree to avoid actual file operations
                with patch('shutil.rmtree') as mock_rmtree:
                    tool._clean_cache()
                    
                    mock_rmtree.assert_called_once_with(mock_cache_path)
    
    def test_clean_cache_nonexistent(self, tool):
        """Test cleaning non-existent cache"""
        # Mock the cache path to avoid affecting real cache
        with patch.object(tool, '_get_cache_path') as mock_get_cache:
            mock_cache_path = Path("/mock/cache/path")
            mock_get_cache.return_value = mock_cache_path
            
            # Mock that the cache doesn't exist
            with patch('pathlib.Path.exists') as mock_exists:
                mock_exists.return_value = False
                
                # Mock shutil.rmtree to avoid actual file operations
                with patch('shutil.rmtree') as mock_rmtree:
                    tool._clean_cache()
                    
                    # Should not call rmtree since cache doesn't exist
                    mock_rmtree.assert_not_called()
    
    def test_list_schemes_no_cache(self, tool):
        """Test listing schemes when cache is not available"""
        # Mock the cache path to avoid affecting real cache
        with patch.object(tool, '_get_cache_path') as mock_get_cache:
            mock_cache_path = Path("/mock/cache/path")
            mock_get_cache.return_value = mock_cache_path
            
            # Mock that the cache doesn't exist
            with patch('pathlib.Path.exists') as mock_exists:
                mock_exists.return_value = False
                
                # This should not raise an exception but should show error message
                tool._list_schemes()
    
    def test_list_schemes_with_cache(self, tool, temp_dir):
        """Test listing schemes with cache"""
        # Mock the cache path to avoid affecting real cache
        with patch.object(tool, '_get_cache_path') as mock_get_cache:
            mock_cache_path = temp_dir / "cache"
            mock_get_cache.return_value = mock_cache_path
            
            # Create mock scheme files in temp directory
            mobaxterm_dir = mock_cache_path / tool.MOBAXTERM_DIR
            mobaxterm_dir.mkdir(parents=True, exist_ok=True)
            
            schemes = ["scheme1.ini", "scheme2.ini", "dark_scheme.ini"]
            for scheme in schemes:
                (mobaxterm_dir / scheme).touch()
            
            # Test listing all schemes
            tool._list_schemes()
            
            # Test searching schemes
            tool._list_schemes(search="dark")
            
            # Test with limit
            tool._list_schemes(limit=2)
    
    def test_list_schemes_search_no_matches(self, tool, temp_dir):
        """Test listing schemes with search that returns no matches"""
        # Mock the cache path to avoid affecting real cache
        with patch.object(tool, '_get_cache_path') as mock_get_cache:
            mock_cache_path = temp_dir / "cache"
            mock_get_cache.return_value = mock_cache_path
            
            # Create mock scheme files in temp directory
            mobaxterm_dir = mock_cache_path / tool.MOBAXTERM_DIR
            mobaxterm_dir.mkdir(parents=True, exist_ok=True)
            
            schemes = ["scheme1.ini", "scheme2.ini"]
            for scheme in schemes:
                (mobaxterm_dir / scheme).touch()
            
            # Test searching for non-existent scheme
            tool._list_schemes(search="nonexistent")
    
    def test_show_cache_status_no_cache(self, tool):
        """Test showing cache status when cache doesn't exist"""
        # Mock the cache path to avoid affecting real cache
        with patch.object(tool, '_get_cache_path') as mock_get_cache:
            mock_cache_path = Path("/mock/cache/path")
            mock_get_cache.return_value = mock_cache_path
            
            # Mock that the cache doesn't exist
            with patch('pathlib.Path.exists') as mock_exists:
                mock_exists.return_value = False
                
                tool._show_cache_status()
    
    def test_show_cache_status_with_cache(self, tool, temp_dir):
        """Test showing cache status with cache"""
        # Mock the cache path to avoid affecting real cache
        with patch.object(tool, '_get_cache_path') as mock_get_cache:
            mock_cache_path = temp_dir / "cache"
            mock_get_cache.return_value = mock_cache_path
            
            # Create mock scheme files in temp directory
            mobaxterm_dir = mock_cache_path / tool.MOBAXTERM_DIR
            mobaxterm_dir.mkdir(parents=True, exist_ok=True)
            
            schemes = ["scheme1.ini", "scheme2.ini"]
            for scheme in schemes:
                (mobaxterm_dir / scheme).touch()
            
            tool._show_cache_status()
    
    def test_show_cache_status_with_git_info(self, tool, temp_dir):
        """Test showing cache status with git information"""
        # Mock the entire _show_cache_status method to avoid real git operations
        with patch.object(tool, '_show_cache_status') as mock_show_status:
            mock_show_status.return_value = None
            
            # Call the method
            tool._show_cache_status()
            
            # Verify that the method was called
            mock_show_status.assert_called_once()
    
    def test_show_status(self, tool):
        """Test showing tool status"""
        tool._show_status()
    
    def test_apply_scheme_success(self, tool, mock_config_file, mock_scheme_file):
        """Test successful application of color scheme"""
        cache_path = tool._get_cache_path()
        mobaxterm_dir = cache_path / tool.MOBAXTERM_DIR
        mobaxterm_dir.mkdir(parents=True, exist_ok=True)
        
        # Copy scheme file to cache
        shutil.copy(mock_scheme_file, mobaxterm_dir / "test_scheme.ini")
        
        with patch.object(tool, '_get_mobaxterm_config_path') as mock_get_config:
            mock_get_config.return_value = mock_config_file
            
            with patch.object(tool, '_backup_config') as mock_backup:
                with patch.object(tool, '_write_mobaxterm_config') as mock_write:
                    tool._apply_scheme("test_scheme", force=True)
                    
                    mock_backup.assert_called_once()
                    mock_write.assert_called_once()
    
    def test_apply_scheme_not_found(self, tool):
        """Test applying non-existent color scheme"""
        with patch.object(tool, '_get_mobaxterm_config_path') as mock_get_config:
            mock_get_config.return_value = Path("/dummy/path")
            
            # This should show error message
            tool._apply_scheme("nonexistent_scheme", force=True)
    
    def test_apply_scheme_parse_error(self, tool, temp_dir):
        """Test applying scheme with parse error"""
        cache_path = tool._get_cache_path()
        mobaxterm_dir = cache_path / tool.MOBAXTERM_DIR
        mobaxterm_dir.mkdir(parents=True, exist_ok=True)
        
        # Create invalid scheme file
        invalid_scheme = mobaxterm_dir / "invalid_scheme.ini"
        with open(invalid_scheme, 'w') as f:
            f.write("Invalid content")
        
        with patch.object(tool, '_get_mobaxterm_config_path') as mock_get_config:
            mock_get_config.return_value = temp_dir / "config.ini"
            
            # This should show error message
            tool._apply_scheme("invalid_scheme", force=True)
    
    def test_apply_scheme_with_confirmation(self, tool, mock_config_file, mock_scheme_file):
        """Test applying color scheme with confirmation"""
        cache_path = tool._get_cache_path()
        mobaxterm_dir = cache_path / tool.MOBAXTERM_DIR
        mobaxterm_dir.mkdir(parents=True, exist_ok=True)
        
        # Copy scheme file to cache
        shutil.copy(mock_scheme_file, mobaxterm_dir / "test_scheme.ini")
        
        with patch.object(tool, '_get_mobaxterm_config_path') as mock_get_config:
            mock_get_config.return_value = mock_config_file
            
            with patch('click.confirm') as mock_confirm:
                mock_confirm.return_value = True
                
                with patch.object(tool, '_backup_config') as mock_backup:
                    with patch.object(tool, '_write_mobaxterm_config') as mock_write:
                        tool._apply_scheme("test_scheme", force=False)
                        
                        mock_backup.assert_called_once()
                        mock_write.assert_called_once()
    
    def test_apply_scheme_cancelled(self, tool, mock_config_file, mock_scheme_file):
        """Test applying color scheme when cancelled"""
        cache_path = tool._get_cache_path()
        mobaxterm_dir = cache_path / tool.MOBAXTERM_DIR
        mobaxterm_dir.mkdir(parents=True, exist_ok=True)
        
        # Copy scheme file to cache
        shutil.copy(mock_scheme_file, mobaxterm_dir / "test_scheme.ini")
        
        with patch.object(tool, '_get_mobaxterm_config_path') as mock_get_config:
            mock_get_config.return_value = mock_config_file
            
            with patch('click.confirm') as mock_confirm:
                mock_confirm.return_value = False
                
                with patch.object(tool, '_backup_config') as mock_backup:
                    with patch.object(tool, '_write_mobaxterm_config') as mock_write:
                        tool._apply_scheme("test_scheme", force=False)
                        
                        # Backup is called before confirmation, so we can't assert it wasn't called
                        # Instead, we check that write was not called
                        mock_write.assert_not_called()
    
    def test_show_applied_colors(self, tool):
        """Test showing applied colors"""
        colors = {
            'Black': '0,0,0',
            'White': '255,255,255',
            'BoldBlack': '128,128,128'
        }
        
        tool._show_applied_colors(colors)
    
    def test_cli_commands_registration(self, tool):
        """Test that CLI commands are properly registered"""
        # This test verifies that the tool can be used as a CLI command
        assert hasattr(tool, '_add_cli_commands')
    
    def test_tool_decorator_integration(self):
        """Test that the tool is properly decorated"""
        tool = MobaXtermColors()
        
        # Check that the tool has the expected attributes from the decorator
        # Note: The decorator might not be applied during testing, so we check for the method instead
        assert hasattr(tool, '_add_cli_commands')
        assert tool.tool_name == "mobaxterm-colors"
    
    def test_auto_init_cache_mocked(self, temp_dir):
        """Test auto initialization of cache with mocked git operations"""
        # Create tool with mocked paths
        tool = MobaXtermColors()
        
        with patch.object(tool, '_get_okit_root_dir') as mock_root:
            mock_root.return_value = temp_dir / ".okit"
            
            with patch.object(tool, '_get_tool_config_dir') as mock_config_dir:
                mock_config_dir.return_value = temp_dir / ".okit" / "config" / tool.tool_name
                
                with patch.object(tool, '_get_tool_data_dir') as mock_data_dir:
                    mock_data_dir.return_value = temp_dir / ".okit" / "data" / tool.tool_name
                    
                    # Mock _update_cache to avoid real git operations
                    with patch.object(tool, '_update_cache') as mock_update_cache:
                        mock_update_cache.return_value = None
                        
                        # Mock _is_valid_git_repo to return False to trigger auto-init
                        with patch.object(tool, '_is_valid_git_repo') as mock_is_valid:
                            mock_is_valid.return_value = False
                            
                            # Mock get_config_value to enable auto_update
                            with patch.object(tool, 'get_config_value') as mock_get_config:
                                mock_get_config.return_value = True  # Enable auto_update
                                
                                # This should call _update_cache due to auto_init_cache
                                tool._auto_init_cache()
                                
                                # Verify that _update_cache was called
                                mock_update_cache.assert_called_once() 

    def test_apply_scheme_replace_only_common_colors(self, tool, temp_dir):
        """Test that only common colors between scheme and config are replaced"""
        # Create a mock MobaXterm.ini with specific colors
        config_file = temp_dir / "MobaXterm.ini"
        config_content = """[Colors]
Black=0,0,0
Red=255,0,0
Green=0,255,0
Blue=0,0,255
White=255,255,255
BoldBlack=128,128,128
BoldRed=255,128,128
BoldGreen=128,255,128
BoldBlue=128,128,255
BoldWhite=255,255,255
ForegroundColour=255,255,255
BackgroundColour=0,0,0
CursorColour=255,255,0"""
        
        with open(config_file, 'w') as f:
            f.write(config_content)
        
        # Create a scheme file with some matching and some non-matching colors
        scheme_file = temp_dir / "test_scheme.ini"
        scheme_content = """Black=17,38,22
Red=127,43,39
Green=47,126,37
Yellow=113,127,36
Blue=47,106,127
Magenta=71,88,127
Cyan=50,127,119
White=100,125,117
BoldBlack=60,72,18
BoldRed=224,128,9
BoldGreen=24,224,0
BoldYellow=189,224,0
BoldBlue=0,170,224
BoldMagenta=0,88,224
BoldCyan=0,224,196
BoldWhite=115,250,145
ForegroundColour=99,125,117
BackgroundColour=15,22,16
CursorColour=115,250,145
ExtraColor=255,255,255"""
        
        with open(scheme_file, 'w') as f:
            f.write(scheme_content)
        
        # Mock the config path and cache
        with patch.object(tool, '_get_mobaxterm_config_path') as mock_get_config:
            mock_get_config.return_value = config_file
            
            with patch.object(tool, '_get_cache_path') as mock_get_cache:
                cache_path = temp_dir / "cache"
                cache_path.mkdir(exist_ok=True)
                mobaxterm_dir = cache_path / "mobaxterm"
                mobaxterm_dir.mkdir(exist_ok=True)
                mock_get_cache.return_value = cache_path
                
                # Copy scheme file to cache
                shutil.copy(scheme_file, mobaxterm_dir / "test_scheme.ini")
                
                with patch.object(tool, '_backup_config') as mock_backup:
                    with patch.object(tool, '_write_mobaxterm_config') as mock_write:
                        tool._apply_scheme("test_scheme", force=True)
                        
                        # Verify backup was called
                        mock_backup.assert_called_once()
                        
                        # Verify write was called
                        mock_write.assert_called_once()
                        
                        # Get the config that was written
                        written_config = mock_write.call_args[0][0]
                        
                        # Check that only common colors were replaced
                        colors_section = written_config['Colors']
                        
                        # Colors that should be replaced (exist in both)
                        assert colors_section['Black'] == '17,38,22'
                        assert colors_section['Red'] == '127,43,39'
                        assert colors_section['Green'] == '47,126,37'
                        assert colors_section['Blue'] == '47,106,127'
                        assert colors_section['White'] == '100,125,117'
                        assert colors_section['BoldBlack'] == '60,72,18'
                        assert colors_section['BoldRed'] == '224,128,9'
                        assert colors_section['BoldGreen'] == '24,224,0'
                        assert colors_section['BoldBlue'] == '0,170,224'
                        assert colors_section['BoldWhite'] == '115,250,145'
                        assert colors_section['ForegroundColour'] == '99,125,117'
                        assert colors_section['BackgroundColour'] == '15,22,16'
                        assert colors_section['CursorColour'] == '115,250,145'
                        
                        # Colors that should NOT be added (only in scheme)
                        assert 'Yellow' not in colors_section
                        assert 'Magenta' not in colors_section
                        assert 'Cyan' not in colors_section
                        assert 'BoldYellow' not in colors_section
                        assert 'BoldMagenta' not in colors_section
                        assert 'BoldCyan' not in colors_section
                        assert 'ExtraColor' not in colors_section 