#include "cx_vision/runtime_contracts.hpp"

#include <iostream>
#include <string>

namespace {

struct Args {
    std::string command;
    std::string state_file;
    std::string config_file;
    std::string session_name;
};

Args ParseArgs(int argc, char** argv) {
    Args args;
    if (argc > 1) {
        args.command = argv[1];
    } else {
        args.command = "status";
    }
    for (int i = 2; i + 1 < argc; i += 2) {
        std::string flag = argv[i];
        if (flag == "--state-file") {
            args.state_file = argv[i + 1];
        } else if (flag == "--config-file") {
            args.config_file = argv[i + 1];
        } else if (flag == "--session-name") {
            args.session_name = argv[i + 1];
        }
    }
    return args;
}

}  // namespace

int main(int argc, char** argv) {
    const Args args = ParseArgs(argc, argv);

    // ── serve mode: long-lived stdin/stdout JSONL process ───────────────
    if (args.command == "serve") {
        std::string session_name = args.session_name;
        if (session_name.empty()) {
            session_name = "cx_vision_runtime";
        }
        return cx_vision::ServeMode(session_name);
    }

    // ── one-shot CLI mode (existing) ────────────────────────────────────
    cx_vision::RuntimeStatus status;

    if (args.command == "start" && !args.config_file.empty()) {
        auto config = cx_vision::ReadRuntimeConfigFile(args.config_file);
        if (!config.valid) {
            status.state = "error";
            status.error_code = config.error_code;
            status.error_message = config.error_message;
            if (!args.state_file.empty()) {
                cx_vision::WriteStateFile(args.state_file, status);
            }
            std::cout << cx_vision::ToJsonLine(status) << '\n';
            return 2;
        }
    }

    if (!args.state_file.empty()) {
        cx_vision::RuntimeStatus disk =
            cx_vision::ReadStateFile(args.state_file);

        if (args.command == "start") {
            if (!disk.error_code.empty()
                && disk.error_code != "STATE_FILE_MISSING") {
                status = disk;
            } else {
                status.state = "running";
                status.uptime_ms = 0;
                status.error_code = "";
                status.error_message = "";
            }
        } else if (args.command == "stop") {
            if (!disk.error_code.empty()
                && disk.error_code != "STATE_FILE_MISSING") {
                status = disk;
            } else {
                status.state = "stopped";
                status.error_code = "";
                status.error_message = "";
            }
        } else if (args.command == "status") {
            if (disk.error_code == "STATE_FILE_MISSING") {
                status.state = "stopped";
                status.error_code = "";
                status.error_message = "";
            } else if (!disk.error_code.empty()) {
                status = disk;
            } else {
                status = disk;
            }
        } else {
            status.state = "error";
            status.error_code = "UNKNOWN_COMMAND";
            status.error_message = "Supported commands: start, stop, status";
        }
    } else {
        if (args.command == "start") {
            status.state = "running";
            status.uptime_ms = 0;
            status.error_code = "";
            status.error_message = "";
        } else if (args.command == "stop") {
            status.state = "stopped";
            status.error_code = "";
            status.error_message = "";
        } else if (args.command == "status") {
            // Keep default stopped.
        } else {
            status.state = "error";
            status.error_code = "UNKNOWN_COMMAND";
            status.error_message = "Supported commands: start, stop, status";
        }
    }

    if (!args.state_file.empty() && status.error_code.empty()) {
        if (!cx_vision::WriteStateFile(args.state_file, status)) {
            status.state = "error";
            status.error_code = "STATE_FILE_WRITE_FAILED";
            status.error_message = args.state_file;
        }
    }

    std::cout << cx_vision::ToJsonLine(status) << '\n';
    return status.state == "error" ? 2 : 0;
}
