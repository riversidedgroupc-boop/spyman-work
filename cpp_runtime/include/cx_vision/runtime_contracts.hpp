#pragma once

#include <cstdint>
#include <string>
#include <vector>

namespace cx_vision {

struct RuntimeStatus {
    std::string state{"stopped"};
    std::int64_t uptime_ms{0};
    int queue_size{0};
    int dropped_frames{0};
    int ng_count{0};
    std::string error_code{};
    std::string error_message{};
};

struct RuntimeConfigSummary {
    std::string run_id{};
    std::string project_id{};
    std::string spec_id{};
    std::string backend{};
    bool valid{false};
    std::string error_code{};
    std::string error_message{};
};

struct DefectEvent {
    std::string event_id{};
    std::string run_id{};
    std::string camera_id{};
    std::int64_t timestamp_ms{0};
    double meter_position{0.0};
    std::string defect_type{};
    double confidence{0.0};
    std::vector<double> bbox_xyxy{};
    std::string image_path{};
    std::string model_version{};
};

std::string ToJsonLine(const RuntimeStatus& status);
std::string ToJsonLine(const DefectEvent& event);

// State-file persistence for one-shot CLI mode.
// Returns STATE_FILE_MISSING when the file does not exist,
// STATE_FILE_INVALID when the file exists but cannot be parsed.
RuntimeStatus ReadStateFile(const std::string& path);
bool WriteStateFile(const std::string& path, const RuntimeStatus& status);

RuntimeConfigSummary ReadRuntimeConfigFile(const std::string& path);

}  // namespace cx_vision
