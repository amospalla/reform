#!/usr/bin/env bash

set -eu -o pipefail -o errtrace

main() {
    local -a command
    local -a extra_commands

    if [[ "${compress:-1}" -eq 1 ]]; then
        extra_commands=("--compress")
    else
        extra_commands=()
    fi

    rm -rf "${mypath}/standalone"
    mkdir "${mypath}/standalone"
    command=(
        rsync
        -a
        "${mypath}/src/"
        "${mypath}/standalone/"
        --exclude=".mypy_cache"
        --exclude="__pycache__"
        --exclude=".idea"
    )
    "${command[@]}"

    if [[ "${PYTHONDONTWRITEBYTECODE:-0}" -eq 1 ]]; then
        find "${mypath}/standalone" -name "*.pyc" -type f -delete
    fi

    command=(
        python3
        -m zipapp
        --python "/usr/bin/env python3"
        "${extra_commands[@]}"
        --output "${mypath}/${standalone_filename}"
        --main "${main}"
        "${mypath}/standalone/"
    )
    "${command[@]}"

    if [[ keep_standalone_folder -eq 0 ]]; then
        rm -rf "${mypath}/standalone/"
    fi

}

export PYTHONDONTWRITEBYTECODE=1

declare mypath
mypath="${0%/*}"
declare package_name="mleds"
declare standalone_filename="mleds"
declare -i compress=1
declare -i keep_standalone_folder=0
declare main="${package_name}.cli:main"

main
