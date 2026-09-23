#if __has_include(<Python/Python.h>)
#include <Python/Python.h>
#else
#include <Python.h>
#endif
#include <stdlib.h>
#include <string.h>
#include "PythonBridge.h"

static char *python_error(void) {
    PyObject *type = NULL, *value = NULL, *trace = NULL;
    PyErr_Fetch(&type, &value, &trace);
    PyErr_NormalizeException(&type, &value, &trace);
    PyObject *message = value ? PyObject_Str(value) : NULL;
    const char *utf8 = message ? PyUnicode_AsUTF8(message) : NULL;
    char *result = strdup(utf8 ? utf8 : "Local Python runtime failed.");
    Py_XDECREF(message); Py_XDECREF(type); Py_XDECREF(value); Py_XDECREF(trace);
    PyErr_Clear();
    return result;
}
char *trainer_python_initialize(const char *home, const char *module_path) {
    if (Py_IsInitialized()) return NULL;
    PyPreConfig pre; PyPreConfig_InitIsolatedConfig(&pre); pre.utf8_mode = 1;
    PyStatus status = Py_PreInitialize(&pre);
    if (PyStatus_Exception(status)) return strdup(status.err_msg ? status.err_msg : "Python preinitialization failed.");
    PyConfig config; PyConfig_InitIsolatedConfig(&config);
    config.write_bytecode = 0; config.buffered_stdio = 0;
    config.install_signal_handlers = 0; config.site_import = 0;
    if (home && home[0]) {
        status = PyConfig_SetBytesString(&config, &config.home, home);
        if (PyStatus_Exception(status)) { PyConfig_Clear(&config); return strdup("Invalid Python home."); }
    }
    status = Py_InitializeFromConfig(&config);
    PyConfig_Clear(&config);
    if (PyStatus_Exception(status)) return strdup(status.err_msg ? status.err_msg : "Python initialization failed.");
    PyObject *path = PyUnicode_DecodeFSDefault(module_path);
    char *error = NULL;
    if (!path || PyList_Insert(PySys_GetObject("path"), 0, path) < 0) error = python_error();
    Py_XDECREF(path);
    PyEval_SaveThread();
    return error;
}
char *trainer_python_call(const char *request, char **error) {
    *error = NULL;
    if (!Py_IsInitialized()) { *error = strdup("Python is not initialized."); return NULL; }
    PyGILState_STATE gil = PyGILState_Ensure();
    PyObject *module = PyImport_ImportModule("ai_trainer.api");
    PyObject *function = module ? PyObject_GetAttrString(module, "dispatch_json") : NULL;
    PyObject *arg = function ? PyUnicode_FromString(request) : NULL;
    PyObject *result = arg ? PyObject_CallFunctionObjArgs(function, arg, NULL) : NULL;
    const char *utf8 = result ? PyUnicode_AsUTF8(result) : NULL;
    char *output = utf8 ? strdup(utf8) : NULL;
    if (!output) *error = python_error();
    Py_XDECREF(result); Py_XDECREF(arg); Py_XDECREF(function); Py_XDECREF(module);
    PyGILState_Release(gil);
    return output;
}
void trainer_python_free(char *value) { free(value); }
