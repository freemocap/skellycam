"""Console script for skellycam."""

import click


@click.command()
def main():
    """Main entrypoint."""
    click.echo("skellycam")
    click.echo("=" * len("skellycam"))
    click.echo("skellycam skellycam")


if __name__ == "__main__":
    main()  # pragma: no cover
