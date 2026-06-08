#include "cx_vision/runtime_contracts.hpp"

#include <atomic>
#include <chrono>
#include <cstdint>
#include <iostream>
#include <sstream>
#include <string>
#include <thread>

namespace cx_vision {
namespace {

// ── helpers ────────────────────────────────────────────────────────────────

std::string BuildEventJson(const std::string& type, const std::string& payload_json) {
    return R"({"type":")" + type + R"(","payload":)" + payload_json + "}";
}

std::string BuildErrorEvent(const std::string& code, const std::string& message) {
    std::ostringstream p;
    p << R"({"code":")" << code << R"(","message":")";
    for (char c : message) {
        if (c == '"') p << "\\\"";
        else if (c == '\\') p << "\\\\";
        else p << c;
    }
    p << R"("})";
    return BuildEventJson("error", p.str());
}

std::string BuildStatusEvent(const RuntimeStatus& st) {
    return BuildEventJson("status", ToJsonLine(st));
}

std::string BuildLogEvent(const std::string& level, const std::string& message) {
    std::ostringstream p;
    p << R"({"level":")" << level << R"(","message":")";
    for (char c : message) {
        if (c == '"') p << "\\\"";
        else if (c == '\\') p << "\\\\";
        else p << c;
    }
    p << R"("})";
    return BuildEventJson("log", p.str());
}

// ── Extract a JSON string value for a top-level key ──────────────────────

std::string ExtractJsonField(const std::string& json, const std::string& key) {
    std::string search = "\"" + key + "\"";
    auto pos = json.find(search);
    if (pos == std::string::npos) return "";
    pos += search.size();
    pos = json.find(':', pos);
    if (pos == std::string::npos) return "";
    ++pos;
    while (pos < json.size() && (json[pos] == ' ' || json[pos] == '\t')) {
        ++pos;
    }
    if (pos >= json.size() || json[pos] != '"') return "";
    ++pos;
    auto end = json.find('"', pos);
    if (end == std::string::npos) return "";
    return json.substr(pos, end - pos);
}

// ── main loop state ───────────────────────────────────────────────────────

struct ServeState {
    std::atomic<bool> running{true};
    std::string state{"idle"};
    std::atomic<std::int64_t> start_time_ms{0};
    std::atomic<int> ng_count{0};
};

bool HandleLine(const std::string& line, ServeState& state) {
    if (line.empty()) return true;

    // Validate JSON input using the same strict parser used for config files.
    if (!cx_vision::ValidateMinimalJsonObject(line)) {
        std::cout << BuildErrorEvent("MALFORMED_JSON", "input is not valid JSON") << '\n';
        return true;
    }

    std::string command = ExtractJsonField(line, "command");
    if (command.empty()) {
        std::cout << BuildErrorEvent("BAD_REQUEST", "missing 'command' field") << '\n';
        return true;
    }

    if (command == "status") {
        RuntimeStatus st;
        st.state = state.state;
        if (state.state == "running") {
            auto now = std::chrono::steady_clock::now().time_since_epoch();
            auto elapsed = std::chrono::duration_cast<std::chrono::milliseconds>(
                               now).count();
            st.uptime_ms = static_cast<std::int64_t>(
                elapsed - state.start_time_ms.load());
            if (st.uptime_ms < 0) st.uptime_ms = 0;
        }
        st.ng_count = state.ng_count.load();
        std::cout << BuildStatusEvent(st) << '\n';
        return true;
    }

    if (command == "start") {
        if (state.state == "running") {
            std::cout << BuildErrorEvent("ALREADY_RUNNING",
                                         "Runtime is already running") << '\n';
            return true;
        }
        std::string config_path = ExtractJsonField(line, "config_path");
        state.state = "running";
        auto now_ms = std::chrono::duration_cast<std::chrono::milliseconds>(
                          std::chrono::steady_clock::now().time_since_epoch())
                          .count();
        state.start_time_ms.store(static_cast<std::int64_t>(now_ms));

        RuntimeStatus st;
        st.state = "running";
        std::cout << BuildStatusEvent(st) << '\n';
        if (!config_path.empty()) {
            std::cout << BuildLogEvent("info",
                                       "start accepted, config_path=" + config_path)
                      << '\n';
        }
        return true;
    }

    if (command == "stop") {
        if (state.state != "running") {
            std::cout << BuildErrorEvent("NOT_RUNNING",
                                         "Runtime is not running") << '\n';
            return true;
        }
        state.state = "idle";
        state.start_time_ms.store(0);
        RuntimeStatus st;
        st.state = "idle";
        std::cout << BuildStatusEvent(st) << '\n';
        return true;
    }

    if (command == "shutdown") {
        std::cout << BuildLogEvent("info", "shutdown acknowledged, goodbye")
                  << '\n';
        state.running.store(false);
        return false;
    }

    std::cout << BuildErrorEvent("UNKNOWN_COMMAND",
                                 "supported: start, stop, status, shutdown")
              << '\n';
    return true;
}

}  // namespace

int ServeMode(const std::string& /*session_name*/) {
    // stdin/stdout protocol: read JSONL commands from stdin, write JSONL
    // events to stdout. The session name is reserved for future diagnostics.
    ServeState state;

    // Send initial idle status.
    RuntimeStatus idle;
    idle.state = "idle";
    std::cout << BuildStatusEvent(idle) << '\n';
    std::cout.flush();

    std::string line;
    while (state.running.load() && std::getline(std::cin, line)) {
        if (!HandleLine(line, state)) {
            break;
        }
        std::cout.flush();
    }

    return 0;
}

}  // namespace cx_vision
