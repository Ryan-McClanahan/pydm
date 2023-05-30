import os
import pytest
from pydm import Display
from pydm.display import load_py_file, _compile_ui_file, _load_compiled_ui_into_display
from qtpy.QtWidgets import QLabel

# The path to the .ui file used in these tests
test_ui_path = os.path.join(
    os.path.dirname(os.path.realpath(__file__)),
    "test_data", "test.ui")

test_ui_with_macros_path = os.path.join(
    os.path.dirname(os.path.realpath(__file__)),
    "test_data", "macro_test.ui"
)

# The path to the .py files used in these tests
no_display_test_py_path = os.path.join(
    os.path.dirname(os.path.realpath(__file__)),
    "test_data", "no_display_test_file.py")

valid_display_test_py_path = os.path.join(
    os.path.dirname(os.path.realpath(__file__)),
    "test_data", "valid_display_test_file.py")


def test_ui_filename_arg(qtbot):
    """If you supply a valid filename argument, you shouldn't get any exceptions."""
    my_display = Display(parent=None, ui_filename=test_ui_path)
    qtbot.addWidget(my_display)


def test_reimplemented_ui_filename(qtbot):
    """If you reimplement ui_filename and return a valid filename, you
    shouldn't get any exceptions."""
    class TestDisplay(Display):
        def ui_filename(self):
            return test_ui_path
    my_display = TestDisplay(parent=None)
    qtbot.addWidget(my_display)


def test_nonexistant_ui_file_raises(qtbot):
    with pytest.raises(IOError):
        my_display = Display(parent=None, ui_filename="this_doesnt_exist.ui")

    class TestDisplay(Display):
        def ui_filename(self):
            return "this_doesnt_exist.ui"

    with pytest.raises(IOError):
        my_display = TestDisplay(parent=None)


def test_nonexistent_py_file_raises():
    """ Load a python file that does not exist and confirm the error raised is as expected """
    with pytest.raises(FileNotFoundError):
        load_py_file('this_doesnt_exist.py')


def test_doesnt_inherit_display_raises():
    """ Load a python file that does not inherit from PyDM Display and confirm the error raised is as expected """
    with pytest.raises(ValueError) as error_info:
        load_py_file(no_display_test_py_path)
    assert 'no class inheriting from Display' in str(error_info.value)


def test_load_valid_python_display_file(qtbot):
    """ Verify that loading a valid python only file inheriting from Display works as expected """
    display = load_py_file(valid_display_test_py_path)
    qtbot.addWidget(display)

    # Confirm that the file loaded everything as expected
    assert display.loaded_file() == valid_display_test_py_path
    assert display.ui_filename() == 'test.ui'
    assert display.macros() == {}
    assert display.previous_display is None
    assert display.next_display is None


def test_load_python_file_with_macros(qtbot):
    """ Attempt to add macros to the display while loading the file """
    macros = {'MACRO_1': 7, 'MACRO_2': 'test_string'}
    display = load_py_file(valid_display_test_py_path, macros=macros)
    qtbot.addWidget(display)
    assert display.loaded_file() == valid_display_test_py_path
    assert display.ui_filename() == 'test.ui'
    assert display.macros() == {'MACRO_1': 7, 'MACRO_2': 'test_string'}


def test_file_path_in_stylesheet_property(qtbot):
    """If you supply a valid filename argument, you shouldn't get any exceptions."""
    my_display = Display(parent=None, ui_filename=test_ui_path)
    qtbot.addWidget(my_display)
    my_display.setStyleSheet("test_stylesheet.css")
    test_css_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "test_data", "test_stylesheet.css")
    with open(test_css_path) as css_file:
        css = css_file.read()
        # Assert that the stylesheet property is populated with the contents of the file.
        assert my_display.styleSheet() == css


def test_stylesheet_property_without_path(qtbot):
    """If you supply a valid filename argument, you shouldn't get any exceptions."""
    my_display = Display(parent=None, ui_filename=test_ui_path)
    qtbot.addWidget(my_display)
    css = "PyDMLabel { font-weight: bold; }"
    my_display.setStyleSheet(css)
    assert my_display.styleSheet() == css


def test_compile_ui_file():
    """
    Does a compile of our test ui file with uic and verifies the correct class is created,
    and the expected methods are added
    """
    code_string, class_name = _compile_ui_file(test_ui_path)
    assert class_name == 'Ui_Form'
    assert 'setupUi(self' in code_string
    assert 'retranslateUi(self' in code_string


def test_load_file_with_macros(qtbot):
    """
    Compiles and loads a ui file containing macros to verify there are no problems. Tests both an individual string
    and a list of strings.
    """
    try:
        # Rather than messing around with adding custom qt widgets just for one test, pretend like a QLabel
        # has a function that sets a value from a string list to verify its correctness
        commands_from_macro = []

        def setCommands(self, commands):
            """ Store what the commands were after macro parsing """
            nonlocal commands_from_macro
            commands_from_macro = commands
        QLabel.setCommands = setCommands

        # Compile the ui file into python code
        macros = {"test_label": "magnet_list",
                  "test_command": "grep -i 'string with spaces'",
                  "test_command_2": "echo hello",
                  "channel_with_dec_option": '.{"dec":{"n": 25}}'}
        code_string, class_name = _compile_ui_file(test_ui_with_macros_path)
        assert class_name == 'Ui_Form'

        # Parse and replace macros, then load into the display
        test_display = Display(macros=macros)
        _load_compiled_ui_into_display(code_string, class_name, test_display, macros)

        # Verify that the macros were replaced correctly
        assert test_display.ui.myLabel.text() == "magnet_list"
        assert test_display.ui.doubleQuotedLabel.text() == '.{"dec":{"n": 25}}'
        assert commands_from_macro == ["grep -i 'string with spaces'", "echo hello"]

    finally:
        del QLabel.setCommands
