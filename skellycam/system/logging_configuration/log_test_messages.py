def log_test_messages(logger):
    logger.trace("This is a TRACE message.")
    logger.debug("This is a DEBUG message.")
    logger.info("This is an INFO message.")
    logger.success("This is a SUCCESS message.")
    logger.api("This is an IMPORTANT message.")
    logger.warning("This is a WARNING message.")
    logger.error("This is an ERROR message.")
    logger.critical("This is a CRITICAL message.")

    print("----------This is a print message.------------------")

    import time

    for iter in range(1, 10):
        wait_time = iter / 10
        print(f"Testing timestamps (round: {iter}:")
        logger.info(
            "Starting 1 sec timer (Δt should probably be near 0, unless you've got other stuff going on)"
        )
        tic = time.perf_counter_ns()
        time.sleep(wait_time)
        toc = time.perf_counter_ns()
        elapsed_time = (toc - tic) / 1e9
        logger.info(
            f"Done {wait_time} sec timer - elapsed time:{elapsed_time} (Δt should be ~{wait_time}s)"
        )
