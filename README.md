# 📁 File Organizer Automation Tool

A Python automation script that automatically sorts files into categorized folders (Documents, Images, Videos, Music, Archives, etc.) based on their file extensions.

## 🚀 Features

- Automatically scans a target directory
- Creates category folders if they don't exist
- Moves files into the correct folders
- Supports common file types
- Easy to customize with additional categories

## 🛠️ Technologies Used

- Python 3
- os
- shutil

## 📂 Project Structure

```text
file-organizer/
│
├── organizer.py
├── README.md
└── target_folder/
    ├── Documents/
    ├── Images/
    ├── Videos/
    └── ...
```

## ▶️ How to Run

### Clone the repository

```bash
git clone https://github.com/yourusername/file-organizer.git
cd file-organizer
```

### Run the script

```bash
python organizer.py
```

## 📌 Example

### Before

```text
Downloads/
├── photo.jpg
├── report.pdf
└── song.mp3
```

### After

```text
Downloads/
├── Images/photo.jpg
├── Documents/report.pdf
└── Music/song.mp3
```

## 📈 Future Improvements

- GUI interface with Tkinter
- Real-time folder monitoring
- Duplicate file detection
- Logging and reporting
