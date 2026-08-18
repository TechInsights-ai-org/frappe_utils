Based on the functionality you've described, I would make the README **practical and technically credible**, not marketing-heavy. Also, I would keep the future AI roadmap clearly separated from the currently implemented utilities so the repository doesn't claim features that aren't there yet.

# frappe_utils

Reusable utilities, integrations, and enhancements for the **Frappe Framework** ecosystem.

`frappe_utils` is a collection of practical utilities developed from real-world Frappe and ERPNext deployments. The project focuses on solving recurring integration, storage, PDF/print, API, and application-level challenges that commonly require custom implementation in Frappe projects.

The goal is to provide reusable components that can be adopted by Frappe developers and organizations instead of repeatedly implementing the same solutions across individual projects.

## Why frappe_utils?

Frappe provides a powerful foundation for building business applications, but real-world deployments often require additional integrations and utilities around the core framework.

Some of the challenges addressed by this project include:

* Managing multiple Google accounts within Frappe applications
* Using different Google Drive accounts for backups and storage
* Integrating multiple Google Calendars
* Improving PDF output and print-format rendering
* Connecting Frappe applications with S3-compatible storage providers
* Supporting cost-effective object-storage providers
* Reusable API improvements and optimizations
* Website and application-level customizations
* Common utilities required across multiple Frappe deployments

## Features

### 🔐 Multi-Account Google Integration

Configure and manage multiple Google accounts from a Frappe application.

This enables use cases such as:

* Multiple Google Drive accounts
* Separate Google Drive backup destinations
* Multiple Google Calendar integrations
* Different Google accounts for different business requirements
* Centralized management of Google OAuth credentials

This is particularly useful for organizations operating multiple sites, environments, teams, or business units where a single Google account is not sufficient.

---

### ☁️ Google Drive Backup

Support for configuring different Google accounts and Google Drive destinations for Frappe backups.

Potential use cases include:

* Separating backups across different Google accounts
* Maintaining independent backup destinations
* Reducing dependency on a single storage account
* Managing backups for multiple Frappe sites

---

### 📅 Multiple Google Calendar Integrations

Support for connecting multiple Google Calendar accounts to Frappe applications.

This allows different teams, users, or business processes to work with separate calendars while maintaining centralized configuration within Frappe.

---

### 📄 Improved PDF & Print Format Handling

Frappe print formats can sometimes render differently in the browser and in generated PDF documents.

`frappe_utils` includes improvements and utilities for handling these rendering issues and producing more consistent PDF output.

The objective is to reduce problems such as:

* Layout differences between browser and PDF
* Alignment issues
* Content positioning problems
* Inconsistent rendering of print formats

---

### 🗄️ S3-Compatible Storage

Integration with S3-compatible object storage providers.

The architecture is intended to support different providers rather than locking deployments to a single storage vendor.

Examples include:

* Amazon S3
* Wasabi
* Other S3-compatible storage providers

This gives organizations more flexibility when choosing storage based on:

* Cost
* Storage requirements
* Infrastructure
* Geographic availability
* Backup strategy

---

### ⚡ API Utilities & Optimizations

Reusable APIs and utilities developed from recurring requirements in Frappe and ERPNext applications.

The intention is to provide commonly required functionality without requiring every project to implement its own solution.

---

### 🌐 Frappe Website Enhancements

Additional website-related customizations and improvements developed while working with Frappe applications.

These utilities are intended to make common website requirements easier to implement and maintain.

---

## Architecture

The project follows the Frappe application architecture and is designed to integrate with existing Frappe sites rather than replace core Frappe functionality.

```text
                    Frappe / ERPNext
                           │
                           │
                    frappe_utils
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
        ▼                  ▼                  ▼
 Google Integrations    Storage           Utilities
        │                  │                  │
   ┌────┼────┐         ┌────┴────┐       ┌────┴─────┐
   │    │    │         │         │       │          │
Drive Calendar OAuth   S3       Wasabi   APIs    Website
```

## Installation

Clone the application into your Frappe Bench:

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app https://github.com/TechInsights-ai-org/frappe_utils.git
```

Install it on your site:

```bash
bench --site your-site-name install-app frappe_utils
```

Run migrations:

```bash
bench --site your-site-name migrate
```

Restart the required services:

```bash
bench restart
```

> Installation instructions may change as the project evolves toward its first public release.

## Configuration

Configuration depends on the individual integration being used.

Typical configuration may include:

* Google OAuth credentials
* Google account information
* Google Drive configuration
* Google Calendar configuration
* S3 endpoint
* S3 access credentials
* S3 bucket
* Region and storage configuration

Credentials should always be stored using appropriate Frappe mechanisms and should never be committed to the repository.

## Use Cases

### Multi-Site Frappe Deployments

Organizations operating multiple Frappe sites can configure independent integrations and storage destinations.

### Backup Management

Different sites or environments can use different Google Drive or S3-compatible storage destinations.

### Cost-Optimized Storage

Organizations can select an S3-compatible provider based on their storage requirements and cost instead of being tied to a single provider.

### ERPNext Custom Applications

Developers can reuse utilities instead of implementing similar integrations repeatedly across ERPNext projects.

### Frappe Development

Developers can use the project as a starting point for common integrations and utilities required when extending Frappe.

## Roadmap

The project is currently focused on reusable Frappe utilities and integrations.

The longer-term vision is to build an **AI layer for the Frappe and ERPNext ecosystem**.

### AI & MCP

Planned AI capabilities include:

* Frappe/ERPNext MCP server
* Reusable MCP tools for Frappe
* AI assistants capable of interacting with Frappe data
* Tool-based AI workflows
* AI skills for Frappe applications

### Frappe Wiki RAG

A planned RAG-based knowledge system for Frappe documentation and Wiki content.

Potential capabilities include:

* Natural-language search across Frappe knowledge
* Context-aware answers
* Documentation discovery
* Technical troubleshooting assistance
* Knowledge-base creation
* Reusable RAG infrastructure for Frappe teams

The intention is to make the knowledge layer reusable so organizations can build their own AI skills and assistants on top of their internal and Frappe-specific knowledge.

### ERPNext Business Agents

Longer-term experiments will explore AI agents operating on top of ERPNext business data.

Potential agents include:

* Strategic Advisor Agent
* Sales Manager Agent
* HR Agent
* Business Insights Agent
* Decision-support assistants

The objective is not simply to add a chatbot, but to create AI systems that can use Frappe/ERPNext data and tools to provide meaningful operational and decision-support capabilities.

## Project Vision

The long-term vision of `frappe_utils` is to evolve from a collection of utilities into a reusable **Frappe ecosystem platform for integrations, developer tooling, knowledge systems, and AI capabilities**.

The project is being developed around real-world problems encountered while building and operating Frappe and ERPNext applications.

The focus is on creating reusable solutions that can eventually benefit the wider Frappe community.

## Current Status

🚧 **Active Development**

The project is currently evolving and some components may change before the first stable public release.

The project is being prepared for wider adoption within the Frappe ecosystem.

## Contributing

Contributions, ideas, bug reports, and improvements are welcome.

If you are working with Frappe or ERPNext and encounter a problem that could be solved as a reusable utility, feel free to open an issue or contribute an implementation.

## License

This project is open source.

See the `LICENSE` file for the applicable license.

## Maintained By

**TechInsights AI**

Building practical utilities and AI capabilities for the Frappe and ERPNext ecosystem.


#### License

mit
