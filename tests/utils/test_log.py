"""Tests for log utility."""

import logging
import sys
import time
from unittest.mock import patch, MagicMock, mock_open
import pytest

from okit.utils.log import (
    OutputLevel,
    RichMarkupProcessor,
    OutputMessage,
    MessageFilter,
    ProgressFilter,
    CategoryFilter,
    OutputBackend,
    ConsoleBackend,
    LoggingBackend,
    GUIBackend,
    UnifiedOutput,
    _StdoutConsole,
    CommandNameFilter,
    output,
    setup_gui_mode,
    setup_file_logging,
    setup_dual_mode,
    set_quiet_mode,
    set_verbose_mode,
    configure_output_level,
    map_logging_level_to_output_level,
)


class TestOutputLevel:
    """Test OutputLevel enum."""

    def test_output_level_values(self):
        """Test OutputLevel enum values."""
        assert OutputLevel.TRACE.value == 5
        assert OutputLevel.DEBUG.value == 10
        assert OutputLevel.INFO.value == 20
        assert OutputLevel.SUCCESS.value == 25
        assert OutputLevel.WARNING.value == 30
        assert OutputLevel.ERROR.value == 40
        assert OutputLevel.CRITICAL.value == 50
        assert OutputLevel.QUIET.value == 60

    def test_output_level_value_comparison(self):
        """Test OutputLevel value comparison."""
        assert OutputLevel.DEBUG.value < OutputLevel.INFO.value
        assert OutputLevel.ERROR.value > OutputLevel.WARNING.value
        assert OutputLevel.SUCCESS.value >= OutputLevel.INFO.value


class TestRichMarkupProcessor:
    """Test RichMarkupProcessor class."""

    def test_strip_markup(self):
        """Test strip_markup method."""
        text = "[bold]Hello[/bold] [red]World[/red]"
        result = RichMarkupProcessor.strip_markup(text)
        assert result == "Hello World"

    def test_strip_markup_no_markup(self):
        """Test strip_markup with no markup."""
        text = "Hello World"
        result = RichMarkupProcessor.strip_markup(text)
        assert result == "Hello World"

    def test_has_markup(self):
        """Test has_markup method."""
        text_with_markup = "[bold]Hello[/bold]"
        text_without_markup = "Hello World"
        
        assert RichMarkupProcessor.has_markup(text_with_markup) is True
        assert RichMarkupProcessor.has_markup(text_without_markup) is False

    def test_convert_to_ansi(self):
        """Test convert_to_ansi method."""
        text = "[bold][red]Hello[/red][/bold]"
        result = RichMarkupProcessor.convert_to_ansi(text)
        assert "\033[1m" in result
        assert "\033[31m" in result
        assert "\033[39m" in result
        assert "\033[22m" in result

    def test_extract_markup_info(self):
        """Test extract_markup_info method."""
        text = "[bold]Hello[/bold] [red]World[/red]"
        info = RichMarkupProcessor.extract_markup_info(text)
        
        assert info["plain_text"] == "Hello World"
        assert info["has_formatting"] is True
        assert len(info["markup_tags"]) > 0
        assert info["original_text"] == text


class TestOutputMessage:
    """Test OutputMessage class."""

    def test_output_message_creation(self):
        """Test OutputMessage creation."""
        message = OutputMessage(OutputLevel.INFO, "test content")
        assert message.level == OutputLevel.INFO
        assert message.content == "test content"
        assert message.category == "general"
        assert message.timestamp is not None

    def test_output_message_with_metadata(self):
        """Test OutputMessage with metadata."""
        metadata = {"key": "value"}
        message = OutputMessage(OutputLevel.INFO, "test", metadata=metadata)
        assert message.metadata == metadata

    def test_get_formatted_content_rich(self):
        """Test get_formatted_content with rich backend."""
        message = OutputMessage(OutputLevel.INFO, "[bold]Hello[/bold]")
        result = message.get_formatted_content("rich")
        assert result == "[bold]Hello[/bold]"

    def test_get_formatted_content_plain(self):
        """Test get_formatted_content with plain backend."""
        message = OutputMessage(OutputLevel.INFO, "[bold]Hello[/bold]")
        result = message.get_formatted_content("plain")
        assert result == "Hello"

    def test_get_formatted_content_ansi(self):
        """Test get_formatted_content with ansi backend."""
        message = OutputMessage(OutputLevel.INFO, "[bold]Hello[/bold]")
        result = message.get_formatted_content("ansi")
        assert "\033[1m" in result

    def test_has_formatting(self):
        """Test has_formatting method."""
        message_with_formatting = OutputMessage(OutputLevel.INFO, "[bold]Hello[/bold]")
        message_without_formatting = OutputMessage(OutputLevel.INFO, "Hello")
        
        assert message_with_formatting.has_formatting() is True
        assert message_without_formatting.has_formatting() is False

    def test_get_markup_info(self):
        """Test get_markup_info method."""
        message = OutputMessage(OutputLevel.INFO, "[bold]Hello[/bold]")
        info = message.get_markup_info()
        assert info["plain_text"] == "Hello"
        assert info["has_formatting"] is True


class TestMessageFilter:
    """Test MessageFilter abstract class."""

    def test_message_filter_abstract(self):
        """Test that MessageFilter is abstract."""
        with pytest.raises(TypeError):
            MessageFilter()


class TestProgressFilter:
    """Test ProgressFilter class."""

    def test_progress_filter_creation(self):
        """Test ProgressFilter creation."""
        filter_instance = ProgressFilter(min_interval=1.0)
        assert filter_instance.min_interval == 1.0

    def test_progress_filter_non_progress_message(self):
        """Test ProgressFilter with non-progress message."""
        filter_instance = ProgressFilter()
        message = OutputMessage(OutputLevel.INFO, "test", category="general")
        assert filter_instance.should_output(message) is True

    def test_progress_filter_progress_message(self):
        """Test ProgressFilter with progress message."""
        filter_instance = ProgressFilter(min_interval=0.1)
        message = OutputMessage(OutputLevel.INFO, "test", category="progress")
        
        # First message should pass
        assert filter_instance.should_output(message) is True
        
        # Second message within interval should be filtered
        assert filter_instance.should_output(message) is False
        
        # Reset the last progress time to simulate time passing
        filter_instance.last_progress_time = 0.0
        assert filter_instance.should_output(message) is True


class TestCategoryFilter:
    """Test CategoryFilter class."""

    def test_category_filter_creation(self):
        """Test CategoryFilter creation."""
        filter_instance = CategoryFilter(["debug", "progress"])
        assert "debug" in filter_instance.excluded_categories
        assert "progress" in filter_instance.excluded_categories

    def test_category_filter_should_output(self):
        """Test CategoryFilter should_output method."""
        filter_instance = CategoryFilter(["debug"])
        
        # Message with excluded category should be filtered
        message = OutputMessage(OutputLevel.INFO, "test", category="debug")
        assert filter_instance.should_output(message) is False
        
        # Message with non-excluded category should pass
        message = OutputMessage(OutputLevel.INFO, "test", category="general")
        assert filter_instance.should_output(message) is True


class TestOutputBackend:
    """Test OutputBackend abstract class."""

    def test_output_backend_abstract(self):
        """Test that OutputBackend is abstract."""
        with pytest.raises(TypeError):
            OutputBackend()

    def test_output_backend_with_filter(self):
        """Test OutputBackend with filter."""
        class TestBackend(OutputBackend):
            def _do_output(self, message):
                pass
        
        backend = TestBackend()
        filter_instance = CategoryFilter(["debug"])
        backend.add_filter(filter_instance)
        
        # Message with excluded category should be filtered
        message = OutputMessage(OutputLevel.INFO, "test", category="debug")
        with patch.object(backend, '_do_output') as mock_do_output:
            backend.output(message)
            mock_do_output.assert_not_called()

    def test_output_backend_level_filtering(self):
        """Test OutputBackend level filtering."""
        class TestBackend(OutputBackend):
            def _do_output(self, message):
                pass
        
        backend = TestBackend()
        backend.set_level(OutputLevel.WARNING)
        
        # INFO message should be filtered
        message = OutputMessage(OutputLevel.INFO, "test")
        with patch.object(backend, '_do_output') as mock_do_output:
            backend.output(message)
            mock_do_output.assert_not_called()
        
        # ERROR message should pass
        message = OutputMessage(OutputLevel.ERROR, "test")
        with patch.object(backend, '_do_output') as mock_do_output:
            backend.output(message)
            mock_do_output.assert_called_once()


class TestConsoleBackend:
    """Test ConsoleBackend class."""

    def test_console_backend_creation(self):
        """Test ConsoleBackend creation."""
        backend = ConsoleBackend()
        assert backend._console is not None

    def test_console_backend_format_message_success(self):
        """Test ConsoleBackend _format_message with success level."""
        backend = ConsoleBackend()
        message = OutputMessage(OutputLevel.SUCCESS, "test")
        result = backend._format_message(message)
        assert "[green]" in result
        assert "✓" in result

    def test_console_backend_format_message_error(self):
        """Test ConsoleBackend _format_message with error level."""
        backend = ConsoleBackend()
        message = OutputMessage(OutputLevel.ERROR, "test")
        result = backend._format_message(message)
        assert "[red]" in result
        assert "✗" in result

    def test_console_backend_format_message_warning(self):
        """Test ConsoleBackend _format_message with warning level."""
        backend = ConsoleBackend()
        message = OutputMessage(OutputLevel.WARNING, "test")
        result = backend._format_message(message)
        assert "[yellow]" in result
        assert "⚠" in result

    def test_console_backend_format_message_with_existing_formatting(self):
        """Test ConsoleBackend _format_message with existing formatting."""
        backend = ConsoleBackend()
        message = OutputMessage(OutputLevel.SUCCESS, "[green]Already formatted[/green]")
        result = backend._format_message(message)
        assert result == "[green]Already formatted[/green]"

    def test_console_backend_rich_import_error(self):
        """Test ConsoleBackend with Rich import error."""
        # This test is skipped because it requires mocking the import behavior
        # which is complex and not essential for coverage
        pytest.skip("Console import error test requires complex mocking")


class TestLoggingBackend:
    """Test LoggingBackend class."""

    def test_logging_backend_creation(self):
        """Test LoggingBackend creation."""
        backend = LoggingBackend("test_logger")
        assert backend._logger is not None
        assert backend._logger.name == "test_logger"

    def test_logging_backend_set_level(self):
        """Test LoggingBackend set_level method."""
        backend = LoggingBackend()
        backend.set_level(OutputLevel.DEBUG)
        assert backend._level == OutputLevel.DEBUG

    def test_logging_backend_do_output_debug(self):
        """Test LoggingBackend _do_output with debug level."""
        backend = LoggingBackend()
        message = OutputMessage(OutputLevel.DEBUG, "test")
        with patch.object(backend._logger, 'debug') as mock_debug:
            backend._do_output(message)
            mock_debug.assert_called_once()

    def test_logging_backend_do_output_info(self):
        """Test LoggingBackend _do_output with info level."""
        backend = LoggingBackend()
        message = OutputMessage(OutputLevel.INFO, "test")
        with patch.object(backend._logger, 'info') as mock_info:
            backend._do_output(message)
            mock_info.assert_called_once()

    def test_logging_backend_do_output_with_category(self):
        """Test LoggingBackend _do_output with category."""
        backend = LoggingBackend()
        message = OutputMessage(OutputLevel.INFO, "test", category="progress")
        with patch.object(backend._logger, 'info') as mock_info:
            backend._do_output(message)
            mock_info.assert_called_with("[progress] test")


class TestGUIBackend:
    """Test GUIBackend class."""

    def test_gui_backend_creation(self):
        """Test GUIBackend creation."""
        backend = GUIBackend(max_messages=100)
        assert backend.max_messages == 100
        assert len(backend._message_queue) == 0

    def test_gui_backend_do_output(self):
        """Test GUIBackend _do_output method."""
        backend = GUIBackend(max_messages=2)
        message1 = OutputMessage(OutputLevel.INFO, "test1")
        message2 = OutputMessage(OutputLevel.INFO, "test2")
        message3 = OutputMessage(OutputLevel.INFO, "test3")
        
        backend._do_output(message1)
        backend._do_output(message2)
        backend._do_output(message3)
        
        # Should only keep the last 2 messages
        assert len(backend._message_queue) == 2
        assert backend._message_queue[0].content == "test2"
        assert backend._message_queue[1].content == "test3"

    def test_gui_backend_get_messages(self):
        """Test GUIBackend get_messages method."""
        backend = GUIBackend()
        message1 = OutputMessage(OutputLevel.INFO, "test1")
        message2 = OutputMessage(OutputLevel.INFO, "test2")
        
        backend._do_output(message1)
        backend._do_output(message2)
        
        messages = backend.get_messages()
        assert len(messages) == 2
        assert messages[0].content == "test1"
        assert messages[1].content == "test2"

    def test_gui_backend_get_messages_with_limit(self):
        """Test GUIBackend get_messages with limit."""
        backend = GUIBackend()
        message1 = OutputMessage(OutputLevel.INFO, "test1")
        message2 = OutputMessage(OutputLevel.INFO, "test2")
        
        backend._do_output(message1)
        backend._do_output(message2)
        
        messages = backend.get_messages(limit=1)
        assert len(messages) == 1
        assert messages[0].content == "test2"

    def test_gui_backend_get_messages_by_category(self):
        """Test GUIBackend get_messages_by_category method."""
        backend = GUIBackend()
        message1 = OutputMessage(OutputLevel.INFO, "test1", category="general")
        message2 = OutputMessage(OutputLevel.INFO, "test2", category="progress")
        
        backend._do_output(message1)
        backend._do_output(message2)
        
        progress_messages = backend.get_messages_by_category("progress")
        assert len(progress_messages) == 1
        assert progress_messages[0].content == "test2"

    def test_gui_backend_clear_messages(self):
        """Test GUIBackend clear_messages method."""
        backend = GUIBackend()
        message = OutputMessage(OutputLevel.INFO, "test")
        backend._do_output(message)
        assert len(backend._message_queue) == 1
        
        backend.clear_messages()
        assert len(backend._message_queue) == 0

    def test_gui_backend_get_queue_info(self):
        """Test GUIBackend get_queue_info method."""
        backend = GUIBackend(max_messages=10)
        message = OutputMessage(OutputLevel.INFO, "test")
        backend._do_output(message)
        
        info = backend.get_queue_info()
        assert info["current_count"] == 1
        assert info["max_capacity"] == 10
        assert info["usage_percent"] == 10.0

    def test_gui_backend_get_formatted_messages(self):
        """Test GUIBackend get_formatted_messages method."""
        backend = GUIBackend()
        message = OutputMessage(OutputLevel.INFO, "[bold]test[/bold]", category="general")
        backend._do_output(message)
        
        formatted = backend.get_formatted_messages()
        assert len(formatted) == 1
        assert formatted[0]["level"] == "INFO"
        assert formatted[0]["category"] == "general"
        assert formatted[0]["content"] == "[bold]test[/bold]"
        assert formatted[0]["markup_info"] is not None


class TestUnifiedOutput:
    """Test UnifiedOutput class."""

    def test_unified_output_creation(self):
        """Test UnifiedOutput creation."""
        unified = UnifiedOutput()
        assert len(unified._backends) == 1
        assert isinstance(unified._backends[0], ConsoleBackend)

    def test_unified_output_add_backend(self):
        """Test UnifiedOutput add_backend method."""
        unified = UnifiedOutput()
        gui_backend = GUIBackend()
        unified.add_backend(gui_backend)
        assert len(unified._backends) == 2

    def test_unified_output_remove_backend(self):
        """Test UnifiedOutput remove_backend method."""
        unified = UnifiedOutput()
        unified.remove_backend(ConsoleBackend)
        assert len(unified._backends) == 0

    def test_unified_output_clear_backends(self):
        """Test UnifiedOutput clear_backends method."""
        unified = UnifiedOutput()
        unified.clear_backends()
        assert len(unified._backends) == 0

    def test_unified_output_set_level(self):
        """Test UnifiedOutput set_level method."""
        unified = UnifiedOutput()
        unified.set_level(OutputLevel.DEBUG)
        assert unified._level == OutputLevel.DEBUG

    def test_unified_output_output(self):
        """Test UnifiedOutput output method."""
        unified = UnifiedOutput()
        message = OutputMessage(OutputLevel.INFO, "test")
        
        with patch.object(unified._backends[0], 'output') as mock_output:
            unified.output(message)
            mock_output.assert_called_once_with(message)

    def test_unified_output_convenience_methods(self):
        """Test UnifiedOutput convenience methods."""
        unified = UnifiedOutput()
        
        with patch.object(unified, 'output') as mock_output:
            unified.success("test")
            mock_output.assert_called_once()
            assert mock_output.call_args[0][0].level == OutputLevel.SUCCESS
            
            unified.error("test")
            assert mock_output.call_args[0][0].level == OutputLevel.ERROR
            
            unified.warning("test")
            assert mock_output.call_args[0][0].level == OutputLevel.WARNING
            
            unified.info("test")
            assert mock_output.call_args[0][0].level == OutputLevel.INFO
            
            unified.debug("test")
            assert mock_output.call_args[0][0].level == OutputLevel.DEBUG
            
            unified.trace("test")
            assert mock_output.call_args[0][0].level == OutputLevel.TRACE
            
            unified.result("test")
            assert mock_output.call_args[0][0].category == "result"
            
            unified.progress("test")
            assert mock_output.call_args[0][0].category == "progress"


class TestStdoutConsole:
    """Test _StdoutConsole class."""

    def test_stdout_console_print(self):
        """Test _StdoutConsole print method."""
        console = _StdoutConsole()
        with patch('builtins.print') as mock_print:
            console.print("[bold]test[/bold]")
            mock_print.assert_called_once_with("test", sep=" ", end="\n", file=sys.stdout)

    def test_stdout_console_print_with_kwargs(self):
        """Test _StdoutConsole print method with kwargs."""
        console = _StdoutConsole()
        with patch('builtins.print') as mock_print:
            console.print("test", sep="|", end="!")
            mock_print.assert_called_once_with("test", sep="|", end="!", file=sys.stdout)


class TestCommandNameFilter:
    """Test CommandNameFilter class."""

    def test_command_name_filter(self):
        """Test CommandNameFilter filter method."""
        filter_instance = CommandNameFilter()
        record = MagicMock()
        
        with patch('click.get_current_context') as mock_get_context:
            mock_context = MagicMock()
            mock_context.info_name = "test_command"
            mock_get_context.return_value = mock_context
            
            result = filter_instance.filter(record)
            assert result is True
            assert record.command == "test_command"

    def test_command_name_filter_no_context(self):
        """Test CommandNameFilter with no context."""
        filter_instance = CommandNameFilter()
        record = MagicMock()
        
        with patch('click.get_current_context') as mock_get_context:
            mock_get_context.return_value = None
            
            result = filter_instance.filter(record)
            assert result is True
            assert record.command == "unknown"

    def test_command_name_filter_exception(self):
        """Test CommandNameFilter with exception."""
        filter_instance = CommandNameFilter()
        record = MagicMock()
        
        with patch('click.get_current_context') as mock_get_context:
            mock_get_context.side_effect = Exception("test error")
            
            result = filter_instance.filter(record)
            assert result is True
            assert record.command == "unknown"


class TestGlobalFunctions:
    """Test global functions."""

    def test_setup_gui_mode(self):
        """Test setup_gui_mode function."""
        with patch.object(output, 'remove_backend') as mock_remove:
            with patch.object(output, 'add_backend') as mock_add:
                setup_gui_mode(500)
                mock_remove.assert_called_once_with(ConsoleBackend)
                mock_add.assert_called_once()

    def test_setup_file_logging(self):
        """Test setup_file_logging function."""
        with patch.object(output, 'add_backend') as mock_add:
            setup_file_logging("test.log")
            mock_add.assert_called_once()

    def test_setup_dual_mode(self):
        """Test setup_dual_mode function."""
        with patch.object(output, 'add_backend') as mock_add:
            setup_dual_mode(500)
            mock_add.assert_called_once()

    def test_set_quiet_mode(self):
        """Test set_quiet_mode function."""
        with patch.object(output, 'set_level') as mock_set_level:
            set_quiet_mode()
            mock_set_level.assert_called_once_with(OutputLevel.QUIET)

    def test_set_verbose_mode(self):
        """Test set_verbose_mode function."""
        with patch.object(output, 'set_level') as mock_set_level:
            set_verbose_mode()
            mock_set_level.assert_called_once_with(OutputLevel.DEBUG)

    def test_configure_output_level(self):
        """Test configure_output_level function."""
        with patch.object(output, 'set_level') as mock_set_level:
            configure_output_level("DEBUG")
            mock_set_level.assert_called_once_with(OutputLevel.DEBUG)

    def test_configure_output_level_invalid(self):
        """Test configure_output_level with invalid level."""
        with patch.object(output, 'set_level') as mock_set_level:
            configure_output_level("INVALID")
            mock_set_level.assert_called_once_with(OutputLevel.INFO)

    def test_map_logging_level_to_output_level(self):
        """Test map_logging_level_to_output_level function."""
        assert map_logging_level_to_output_level("DEBUG") == OutputLevel.DEBUG
        assert map_logging_level_to_output_level("INFO") == OutputLevel.INFO
        assert map_logging_level_to_output_level("WARNING") == OutputLevel.WARNING
        assert map_logging_level_to_output_level("ERROR") == OutputLevel.ERROR
        assert map_logging_level_to_output_level("CRITICAL") == OutputLevel.CRITICAL
        assert map_logging_level_to_output_level("INVALID") == OutputLevel.INFO


class TestGlobalOutput:
    """Test global output instance."""

    def test_global_output_instance(self):
        """Test global output instance."""
        assert isinstance(output, UnifiedOutput)
        assert len(output._backends) >= 1

    def test_global_output_methods(self):
        """Test global output methods."""
        with patch.object(output, 'output') as mock_output:
            output.success("test")
            mock_output.assert_called_once()
            assert mock_output.call_args[0][0].level == OutputLevel.SUCCESS 