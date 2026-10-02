@cli.command(context_settings={'ignore_unknown_options': True})
@click.pass_context
@click.argument('commandline', nargs=-1, type=click.UNPROCESSED)
def run(ctx, commandline):
    # type: (click.Context, List[str]) -> None
    """Run command with environment variables present."""
    file = ctx.obj['FILE']
    dotenv_as_dict = dotenv_values(file)
    if not commandline:
        click.echo('No command given.')
        exit(1)
    ret = run_command(commandline, dotenv_as_dict)  # type: ignore
    exit(ret)
