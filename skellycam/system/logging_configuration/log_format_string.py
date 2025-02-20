LOG_POINTER_STRING = "└>>"
LOG_FORMAT_STRING = LOG_POINTER_STRING + (
    " %(message)s "
    "|-<%(levelname)8s>┤ "
    "%(delta_t)10s | "
    "%(name)s.%(funcName)s():%(lineno)s | "
    "%(asctime)s | "
    "%(pid_color)sPID:%(process)d:%(processName)s\033[0m | "
    "%(tid_color)sTID:%(thread)d:%(threadName)s\033[0m"
)
