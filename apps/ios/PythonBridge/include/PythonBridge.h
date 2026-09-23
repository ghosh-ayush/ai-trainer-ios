#ifndef AI_TRAINER_PYTHON_BRIDGE_H
#define AI_TRAINER_PYTHON_BRIDGE_H
// Process-wide interpreter, serialized by the Swift adapter. Returned strings are owned.
char *trainer_python_initialize(const char *home, const char *module_path);
char *trainer_python_call(const char *request, char **error);
void trainer_python_free(char *value);
#endif
