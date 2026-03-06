import re


def prompt_generate(possible_live_types, prompt=""):
    marker_map = {
        "festival": "team live battle",
        "challenge": "challenge live",
        "medley": "medley live",
    }

    lines = prompt.splitlines()
    filtered_lines = []
    marker_pattern = re.compile(r"^<-!\s*(\w+)\s*!->(.*)")

    for line in lines:
        marker_match = marker_pattern.match(line)
        if marker_match:
            marker = marker_match.group(1).lower()
            rest_of_line = marker_match.group(2)
            live_type = marker_map.get(marker)

            if live_type and live_type in possible_live_types:
                # Keep the line content without the marker, preserving trailing spaces
                filtered_lines.append(rest_of_line)
            # else: skip the line (marker not in possible live types)
        else:
            # Regular line, keep it
            filtered_lines.append(line)

    return "\n".join(filtered_lines)
