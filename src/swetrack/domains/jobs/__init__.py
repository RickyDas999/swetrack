"""Job Radar: discovery, normalization, and (in later checkpoints) persistence of
job postings from external ATS sources.

See docs/job-radar-integration-plan.md for the full checkpoint plan. This
package starts empty of persistence/scoring concerns on purpose --
Checkpoint 1 (adapters -> NormalizedJob) lands first, Checkpoint 2
(discovered_jobs persistence, dedup) after.
"""

from __future__ import annotations
