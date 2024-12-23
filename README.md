# Index Wrapper

Index Wrapper is a Python-based tool designed to download, process, and upload files from various sources. It supports multiple site types, HTTP authentication, and cloud uploads.

## Features

- Download files from various sources
- Process and decompress downloaded files
- Upload files to cloud storage
- Support for HTTP authentication
- Configurable simultaneous downloads
- Progress tracking with rich progress bars

## Requirements

- Python 3.12 or higher
- Docker (optional, for containerized deployment)

## Installation

1. Clone the repository:
    ```sh
    git clone https://github.com/mau671/index-wrapper.git
    cd index-wrapper
    ```

2. Create and activate a virtual environment:
    ```sh
    python -m venv venv
    source venv/bin/activate  # On Windows use `venv\Scripts\activate`
    ```

3. Install the dependencies:
    ```sh
    todo
    ```

4. Copy the example environment file and configure it:
    ```sh
    cp .env.example .env
    # Edit .env with your preferred settings
    ```

## Usage

To run the main script, use the following command:
```sh
python main.py --url <URL> --site_type <SITE_TYPE> [options]
```

### Command Line Options

- `--url`: The URL to download files from.
- `--site_type`: The type of site (e.g., GoIndex, OneDrive).
- `--use_auth`: Whether to use HTTP authentication (default: False).
- `--simultaneous`: Number of simultaneous downloads (default: 4).
- `--delete_after`: Whether to delete files after decompression (default: False).
- `--upload`: Whether to upload files to a cloud (default: False).
- `--group_name`: Group name for cloud upload.
- `--limit`: Limit of files to download per batch.
- `--stats_one_line`: Whether to show progress in a single line (default: False).
- `--last`: Number of last files to download.
- `--base_folder`: Base folder for downloading and processing files.

### Example

```sh
python main.py --url "https://example.com/files" --site_type "achrou/goindex" --use_auth --simultaneous 5 --delete_after --upload --group_name "MyGroup" --limit 10 --stats_one_line --last 5 --base_folder "/downloads"
```

## Docker

To build and run the project using Docker:

1. Build the Docker image:
    ```sh
    docker build -t index-wrapper .
    ```

2. Run the Docker container:
    ```sh
    docker run --env-file .env -v /path/to/downloads:/app/downloads index-wrapper
    ```

## Contributing

Contributions are welcome! Please fork the repository and submit a pull request.

## License

This project is licensed under the MIT License. See the [LICENSE](./LICENSE) file for details.
