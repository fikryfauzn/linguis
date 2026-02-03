# Linguis

A Linux desktop application for reading documents with instant word translation.

## What It Does

Linguis is a document reader that shows word definitions when you select text. Built for Linux with Wayland support, it focuses on providing a simple, distraction-free reading experience with integrated dictionary lookup.

## Core Features

- Read PDF and EPUB documents
- Select any word to see its definition instantly
- Offline dictionary lookup (no internet required)
- Remembers your reading position
- Adjustable zoom levels
- Clean, minimal interface

## Platform

- Operating System: Linux only
- Display Protocol: Wayland
- Desktop Environment: KDE Plasma (primary target)
- Language: Python with PyQt6

## Architecture

Built using the MVVM (Model-View-ViewModel) pattern:

- Models: Document parsing, dictionary lookup, state persistence
- ViewModels: Application logic and async coordination
- Views: Qt-based user interface

## Status

Currently in active development. This is an MVP (Minimum Viable Product) implementation focusing on core functionality.

## License

To be determined.