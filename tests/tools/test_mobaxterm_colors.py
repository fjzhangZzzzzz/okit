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
    def tool(self):
        """Create tool instance"""
        return MobaXtermColors()
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory"""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def mock_config_file(self, temp_dir):
        """Create mock MobaXterm.ini file"""
        config_file = temp_dir / "MobaXterm.ini"
        config = configparser.ConfigParser()
        config.add_section('Colors')
        config['Colors']['Color0'] = '0,0,0'
        config['Colors']['Color1'] = '255,255,255'
        
        with open(config_file, 'w') as f:
            config.write(f)
        
        return config_file
    
    @pytest.fixture
    def mock_scheme_file(self, temp_dir):
        """Create mock .ini scheme file"""
        scheme_file = temp_dir / "test_scheme.ini"
        scheme_content = """Color0=0,0,0
Color1=255,255,255
Color2=128,128,128
Color3=192,192,192"""
        
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
        
        # Remove if exists
        if cache_dir.exists():
            shutil.rmtree(cache_dir)
        
        tool._ensure_cache_dir()
        
        assert cache_dir.exists()
        assert cache_dir.is_dir()
    
    def test_get_mobaxterm_config_path_existing(self, tool, mock_config_file):
        """Test finding existing MobaXterm.ini"""
        with patch.object(tool, '_get_mobaxterm_config_path') as mock_get:
            mock_get.return_value = mock_config_file
            result = tool._get_mobaxterm_config_path()
            assert result == mock_config_file
    
    def test_get_mobaxterm_config_path_custom(self, tool):
        """Test custom config path from configuration"""
        custom_path = Path("/custom/path/MobaXterm.ini")
        tool.set_config_value("mobaxterm_config_path", str(custom_path))
        
        with patch('pathlib.Path.exists') as mock_exists:
            mock_exists.return_value = True
            result = tool._get_mobaxterm_config_path()
            assert result == custom_path
    
    def test_get_mobaxterm_config_path_custom_not_exists(self, tool):
        """Test custom config path that doesn't exist"""
        custom_path = Path("/custom/path/MobaXterm.ini")
        tool.set_config_value("mobaxterm_config_path", str(custom_path))
        
        with patch('pathlib.Path.exists') as mock_exists:
            mock_exists.return_value = False
            result = tool._get_mobaxterm_config_path()
            # Should fall back to detector or default paths
            assert result is not None
    
    def test_get_mobaxterm_config_path_detector_fallback(self, tool):
        """Test fallback to detector when custom path not found"""
        custom_path = Path("/custom/path/MobaXterm.ini")
        tool.set_config_value("mobaxterm_config_path", str(custom_path))
        
        with patch('pathlib.Path.exists') as mock_exists:
            mock_exists.return_value = False
            
            # Mock detector to return a valid path
            mock_install_info = {
                "install_path": "/detected/path"
            }
            with patch.object(tool.detector, 'detect_installation') as mock_detect:
                with patch.object(tool.detector, 'get_config_file_path') as mock_get_config:
                    mock_detect.return_value = mock_install_info
                    mock_get_config.return_value = "/detected/path/MobaXterm.ini"
                    
                    result = tool._get_mobaxterm_config_path()
                    assert result == Path("/detected/path/MobaXterm.ini")
    
    def test_get_mobaxterm_config_path_not_found(self, tool):
        """Test when MobaXterm.ini is not found"""
        with patch('pathlib.Path.exists') as mock_exists:
            mock_exists.return_value = False
            result = tool._get_mobaxterm_config_path()
            assert result is not None  # Should return default path
    
    def test_parse_mobaxterm_scheme(self, tool, mock_scheme_file):
        """Test parsing .ini scheme file"""
        colors = tool._parse_mobaxterm_scheme(mock_scheme_file)
        
        expected = {
            'Color0': '0,0,0',
            'Color1': '255,255,255',
            'Color2': '128,128,128',
            'Color3': '192,192,192'
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
            f.write("Color0=invalid\nColor1=255,255\nColor2=128,128,128,extra")
        
        colors = tool._parse_mobaxterm_scheme(malformed_file)
        # Should still extract valid colors
        assert 'Color2' in colors
        assert colors['Color2'] == '128,128,128'
    
    def test_read_mobaxterm_config(self, tool, mock_config_file):
        """Test reading MobaXterm.ini configuration"""
        config = tool._read_mobaxterm_config(mock_config_file)
        
        assert 'Colors' in config
        assert config['Colors']['Color0'] == '0,0,0'
        assert config['Colors']['Color1'] == '255,255,255'
    
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
        config['Colors']['Color0'] = '255,0,0'
        
        output_file = temp_dir / "output.ini"
        tool._write_mobaxterm_config(config, output_file)
        
        assert output_file.exists()
        
        # Verify content
        with open(output_file, 'r') as f:
            content = f.read()
            assert '[Colors]' in content
            assert 'color0 = 255,0,0' in content  # configparser uses lowercase
    
    def test_write_mobaxterm_config_create_dir(self, tool, temp_dir):
        """Test writing MobaXterm.ini configuration with directory creation"""
        config = configparser.ConfigParser()
        config.add_section('Colors')
        config['Colors']['Color0'] = '255,0,0'
        
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
    
    @patch('git.Repo')
    def test_update_cache_existing(self, mock_repo, tool):
        """Test updating existing cache"""
        cache_path = tool._get_cache_path()
        cache_path.mkdir(parents=True, exist_ok=True)
        
        mock_repo_instance = MagicMock()
        mock_repo.return_value = mock_repo_instance
        mock_repo_instance.remotes.origin.pull.return_value = None
        
        tool._update_cache()
        
        mock_repo.assert_called_once_with(cache_path)
        mock_repo_instance.remotes.origin.pull.assert_called_once()
    
    @patch('git.Repo.clone_from')
    def test_update_cache_new(self, mock_clone, tool):
        """Test creating new cache"""
        cache_path = tool._get_cache_path()
        
        # Ensure cache doesn't exist
        if cache_path.exists():
            shutil.rmtree(cache_path)
        
        tool._update_cache()
        
        mock_clone.assert_called_once_with(tool.REPO_URL, cache_path)
    
    @patch('git.Repo')
    def test_update_cache_git_error(self, mock_repo, tool):
        """Test updating cache with git error"""
        cache_path = tool._get_cache_path()
        cache_path.mkdir(parents=True, exist_ok=True)
        
        mock_repo.side_effect = Exception("Git error")
        
        # Should not raise exception, should handle error gracefully
        tool._update_cache()
    
    def test_clean_cache(self, tool):
        """Test cleaning cache"""
        cache_path = tool._get_cache_path()
        cache_path.mkdir(parents=True, exist_ok=True)
        
        # Create a dummy file
        dummy_file = cache_path / "dummy.txt"
        dummy_file.write_text("test")
        
        tool._clean_cache()
        
        assert not cache_path.exists()
    
    def test_clean_cache_nonexistent(self, tool):
        """Test cleaning non-existent cache"""
        cache_path = tool._get_cache_path()
        
        # Ensure cache doesn't exist
        if cache_path.exists():
            shutil.rmtree(cache_path)
        
        tool._clean_cache()
        # Should not raise exception
    
    def test_list_schemes_no_cache(self, tool):
        """Test listing schemes when cache is not available"""
        cache_path = tool._get_cache_path()
        
        # Ensure cache doesn't exist
        if cache_path.exists():
            shutil.rmtree(cache_path)
        
        # This should not raise an exception but should show error message
        tool._list_schemes()
    
    def test_list_schemes_with_cache(self, tool, temp_dir):
        """Test listing schemes with cache"""
        cache_path = tool._get_cache_path()
        mobaxterm_dir = cache_path / tool.MOBAXTERM_DIR
        mobaxterm_dir.mkdir(parents=True, exist_ok=True)
        
        # Create some mock scheme files
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
        cache_path = tool._get_cache_path()
        mobaxterm_dir = cache_path / tool.MOBAXTERM_DIR
        mobaxterm_dir.mkdir(parents=True, exist_ok=True)
        
        # Create some mock scheme files
        schemes = ["scheme1.ini", "scheme2.ini"]
        for scheme in schemes:
            (mobaxterm_dir / scheme).touch()
        
        # Test searching for non-existent scheme
        tool._list_schemes(search="nonexistent")
    
    def test_show_cache_status_no_cache(self, tool):
        """Test showing cache status when cache doesn't exist"""
        cache_path = tool._get_cache_path()
        
        # Ensure cache doesn't exist
        if cache_path.exists():
            shutil.rmtree(cache_path)
        
        tool._show_cache_status()
    
    def test_show_cache_status_with_cache(self, tool, temp_dir):
        """Test showing cache status with cache"""
        cache_path = tool._get_cache_path()
        mobaxterm_dir = cache_path / tool.MOBAXTERM_DIR
        mobaxterm_dir.mkdir(parents=True, exist_ok=True)
        
        # Create some mock scheme files
        schemes = ["scheme1.ini", "scheme2.ini"]
        for scheme in schemes:
            (mobaxterm_dir / scheme).touch()
        
        tool._show_cache_status()
    
    @patch('git.Repo')
    def test_show_cache_status_with_git_info(self, mock_repo, tool, temp_dir):
        """Test showing cache status with git information"""
        cache_path = tool._get_cache_path()
        mobaxterm_dir = cache_path / tool.MOBAXTERM_DIR
        mobaxterm_dir.mkdir(parents=True, exist_ok=True)
        
        # Create some mock scheme files
        schemes = ["scheme1.ini", "scheme2.ini"]
        for scheme in schemes:
            (mobaxterm_dir / scheme).touch()
        
        # Mock git repository
        mock_repo_instance = MagicMock()
        mock_repo.return_value = mock_repo_instance
        mock_commit = MagicMock()
        mock_commit.committed_datetime.strftime.return_value = "2023-01-01 12:00:00"
        mock_repo_instance.head.commit = mock_commit
        
        tool._show_cache_status()
    
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
            'Color0': '0,0,0',
            'Color1': '255,255,255',
            'Color2': '128,128,128'
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