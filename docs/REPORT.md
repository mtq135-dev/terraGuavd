# TerraGuavd project report

The current plain edition uses white pages, black headings, simple table formatting and editable text for the cover and chapter dividers. Report body text and database attribute tables are preserved. All 79 pages were rendered and reviewed, and 113 page references were refreshed.

- [Word report](TerraGuavd_Project_Report_Plain.docx)
- [PDF report](TerraGuavd_Project_Report_Plain.pdf)
- [PlantUML source and rendered diagrams](TerraGuavd_PlantUML_Plain.zip)
- [Individual editable diagram sources](plantuml-plain/)

Screenshots use the application's actual Light appearance. The UAV information modal includes the application's normal dimmed backdrop. Screenshot values are retained local simulation records.

The database section documents the fleet schema through local migration 0008. Approval records and alert metadata introduced by the later GitHub integration require a separate content update; see [the consistency review](consistency-review.md). The report's testing/evaluation and conclusion content remains unchanged.

The branch includes a local migration-history integration: fleet migrations occupy 0007/0008 and upstream alert/approval migrations follow as 0009/0010. Review that history before using this branch with a database already stamped with upstream's alternative 0007/0008 migrations.
