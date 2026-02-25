"""
Command-line interface for the Asclepius biological data infrastructure.

Usage examples
--------------
# Initialise a new SQLite database at the default path
python -m asclepius init

# List all experiments stored in the database
python -m asclepius experiments list

# Show version history for a specific experiment
python -m asclepius experiments versions EXP_001

# Show all batches for an experiment
python -m asclepius batches list --experiment EXP_001

# Show all perturbations
python -m asclepius perturbations list

# Show ontology terms (optionally filtered by namespace)
python -m asclepius ontology list --namespace GO
python -m asclepius ontology list --no-deprecated
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from asclepius.storage.database import Database


_DEFAULT_DB = Path("asclepius.db")


def _db(args: argparse.Namespace) -> Database:
    return Database(args.db)


# ------------------------------------------------------------------ #
# Sub-command handlers                                                #
# ------------------------------------------------------------------ #


def cmd_init(args: argparse.Namespace) -> None:
    db_path = Path(args.db)
    Database(db_path)
    print(f"Initialised database: {db_path.resolve()}")


def cmd_experiments_list(args: argparse.Namespace) -> None:
    db = _db(args)
    experiments = db.list_experiments()
    if not experiments:
        print("No experiments found.")
        return
    for exp in experiments:
        print(
            f"{exp.experiment_id}  |  {exp.name}  |  "
            f"{exp.genome_assembly}/{exp.annotation_version}  |  "
            f"samples={len(exp.samples)}  |  hash={exp.content_hash()[:12]}..."
        )


def cmd_experiments_versions(args: argparse.Namespace) -> None:
    db = _db(args)
    history = db.get_version_history(args.experiment_id)
    if not history:
        print(f"No version history found for '{args.experiment_id}'.")
        return
    print(f"Version history for experiment '{args.experiment_id}':")
    for i, entry in enumerate(history, 1):
        print(f"  v{i:>3d}  {entry['recorded_at']}  {entry['content_hash'][:16]}...")


def cmd_batches_list(args: argparse.Namespace) -> None:
    db = _db(args)
    batches = db.list_batches(experiment_id=args.experiment)
    if not batches:
        print("No batches found.")
        return
    for b in batches:
        print(
            f"{b.batch_id}  |  {b.experiment_id}  |  "
            f"{b.sequencing_platform}  |  {b.sequencing_date}"
        )


def cmd_perturbations_list(args: argparse.Namespace) -> None:
    db = _db(args)
    perts = db.list_perturbations()
    if not perts:
        print("No perturbations found.")
        return
    for p in perts:
        print(
            f"{p.perturbation_id}  |  {p.perturbation_type.value}  |  {p.name}"
        )


def cmd_ontology_list(args: argparse.Namespace) -> None:
    from asclepius.models.ontology import OntologyNamespace

    db = _db(args)
    ns = OntologyNamespace(args.namespace) if args.namespace else None
    terms = db.list_ontology_terms(
        namespace=ns, include_deprecated=not args.no_deprecated
    )
    if not terms:
        print("No ontology terms found.")
        return
    for t in terms:
        deprecated_flag = " [DEPRECATED]" if t.is_deprecated else ""
        print(f"{t.term_id}  |  {t.namespace.value}  |  {t.label}{deprecated_flag}")


# ------------------------------------------------------------------ #
# Parser construction                                                 #
# ------------------------------------------------------------------ #


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="asclepius",
        description="Asclepius Research Labs – Biological Data Infrastructure CLI",
    )
    parser.add_argument(
        "--db",
        default=str(_DEFAULT_DB),
        metavar="PATH",
        help="Path to the SQLite database file (default: asclepius.db)",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    # init
    sub.add_parser("init", help="Initialise a new database.")

    # experiments
    exp_parser = sub.add_parser("experiments", help="Manage RNA-seq experiments.")
    exp_sub = exp_parser.add_subparsers(dest="subcommand", required=True)
    exp_sub.add_parser("list", help="List all experiments.")
    ver_p = exp_sub.add_parser("versions", help="Show version history for an experiment.")
    ver_p.add_argument("experiment_id")

    # batches
    batch_parser = sub.add_parser("batches", help="Manage sequencing batches.")
    batch_sub = batch_parser.add_subparsers(dest="subcommand", required=True)
    bl = batch_sub.add_parser("list", help="List batches.")
    bl.add_argument("--experiment", default=None, help="Filter by experiment ID.")

    # perturbations
    pert_parser = sub.add_parser("perturbations", help="Manage perturbations.")
    pert_sub = pert_parser.add_subparsers(dest="subcommand", required=True)
    pert_sub.add_parser("list", help="List all perturbations.")

    # ontology
    onto_parser = sub.add_parser("ontology", help="Browse ontology terms.")
    onto_sub = onto_parser.add_subparsers(dest="subcommand", required=True)
    ol = onto_sub.add_parser("list", help="List ontology terms.")
    ol.add_argument("--namespace", default=None, help="Filter by namespace (e.g. GO, DOID).")
    ol.add_argument(
        "--no-deprecated",
        action="store_true",
        default=False,
        help="Exclude deprecated terms.",
    )

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    dispatch = {
        ("init", None): cmd_init,
        ("experiments", "list"): cmd_experiments_list,
        ("experiments", "versions"): cmd_experiments_versions,
        ("batches", "list"): cmd_batches_list,
        ("perturbations", "list"): cmd_perturbations_list,
        ("ontology", "list"): cmd_ontology_list,
    }

    key = (args.command, getattr(args, "subcommand", None))
    handler = dispatch.get(key)
    if handler is None:
        parser.print_help()
        sys.exit(1)
    handler(args)


if __name__ == "__main__":
    main()
