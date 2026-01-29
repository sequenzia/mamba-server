# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- Add "main" general-purpose agent for versatile chat conversations
- Add `mamba_agent.enable_streaming` configuration setting to toggle between streaming and non-streaming Mamba agent execution

### Changed
- Change Mamba agents to use non-streaming execution by default for simpler and more reliable behavior

### Fixed
- Fix Mamba agent streaming with multiple tool calls terminating prematurely after first tool execution
