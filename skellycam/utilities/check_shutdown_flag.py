import os


def get_server_shutdown_environment_flag():
    flag = os.getenv("SKELLYCAM_SHOULD_SHUTDOWN")
    if flag:
        for _ in range(20):
            print(f"SHUTDOWN FLAG DETECTED! os.getenv('SKELLYCAM_SHOULD_SHUTDOWN'): {flag}")
    return flag
