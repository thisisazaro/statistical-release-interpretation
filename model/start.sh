#!/bin/bash
# Start the study's local OpenAI-compatible endpoint on an Apple Silicon Mac.
# Run once per experiment in its own terminal. Stop with Ctrl-C.
# Optionally set STATGAZER_RUNTIME_TGZ and STATGAZER_MODEL_FILE to existing files.
set -euo pipefail

if [[ "$(uname -s)" != Darwin || "$(uname -m)" != arm64 ]]; then
    echo "The pinned runtime requires Apple Silicon macOS." >&2
    exit 1
fi

release=b8177
revision=bc640142c66e1fdd12af0bd68f40445458f3869b
archive_sha=2836aa9543665b19f9dfc6be1d941a41b939529fe55cdc7266742d93ac28ad26
server_sha=6750c2ff4395215e9bfeb9e1c7c33d523a7a8988388400a4f51eece6ef451416
weight_sha=7485fe6f11af29433bc51cab58009521f205840f5b4ae3a32fa7f92e8534fdf5
archive_name="llama-${release}-bin-macos-arm64.tar.gz"
weight_name="Qwen3-4B-Q4_K_M.gguf"
cache_dir="${XDG_CACHE_HOME:-$HOME/Library/Caches}/statgazer/statistical-release-interpretation"
mkdir -p "$cache_dir"
run_dir="$(mktemp -d "$cache_dir/run.XXXXXXXX")"
trap 'rm -rf "$run_dir"' EXIT

verify() {
    local path=$1 expected=$2 line
    line="$(shasum -a 256 "$path")" || return 1
    [[ "${line%% *}" == "$expected" ]]
}

# Retrieve an immutable artifact, preferring explicitly supplied or already
# available copies. Publish fresh downloads in the cache only after verification.
artifact() {
    local override=$1 original=$2 name=$3 url=$4 sha=$5 file
    if [[ -n "$override" ]]; then
        file="$override"
    elif [[ -f "$cache_dir/$name" ]]; then
        file="$cache_dir/$name"
    elif [[ -f "$original" ]] && verify "$original" "$sha"; then
        printf '%s\n' "$original"
        return
    else
        file="$run_dir/$name"
        curl --fail --location --retry 3 --output "$file" "$url" >&2 || return 1
    fi
    if [[ ! -f "$file" ]] || ! verify "$file" "$sha"; then
        echo "Missing file or SHA-256 mismatch: $file" >&2
        return 1
    fi
    if [[ "$file" == "$run_dir/$name" ]]; then
        mv -f "$file" "$cache_dir/$name" || return 1
        file="$cache_dir/$name"
    fi
    printf '%s\n' "$file"
}

archive="$(artifact "${STATGAZER_RUNTIME_TGZ:-}" /private/tmp/statgazer-revision-runtime/runtime.tgz "$archive_name" \
    "https://github.com/ggml-org/llama.cpp/releases/download/$release/$archive_name" "$archive_sha")"
weights="$(artifact "${STATGAZER_MODEL_FILE:-}" /private/tmp/statgazer-revision-model/qwen3-4b.gguf "$weight_name" \
    "https://huggingface.co/Qwen/Qwen3-4B-GGUF/resolve/$revision/$weight_name" "$weight_sha")"

# The release includes llama-server and matching Metal/ggml dynamic libraries.
tar -xzf "$archive" -C "$run_dir"
server="$run_dir/llama-$release/llama-server"
if ! verify "$server" "$server_sha"; then
    echo "Unexpected llama-server executable in the pinned runtime." >&2
    exit 1
fi
"$server" -m "$weights" --host 127.0.0.1 --port 18197 -c 4096 -ngl 99 -np 1 --jinja --alias qwen3-4b
