import click

from omim.core.downloads import OmimDownloads, FILES
from omim.core.api import ApiKeyError


__epilog__ = click.style('''

\b
examples:
    omim download                      # download/check all 4 files
    omim download genemap2 morbidmap    # only specific files
    omim download -o ./data            # save into ./data
    omim download --force              # re-download even if up to date
''', fg='yellow')


@click.command(name='download',
               help=click.style('download official OMIM text files', fg='green'),
               epilog=__epilog__)
@click.option('-k', '--api-key', help='OMIM API key (also the download token)')
@click.option('-o', '--outdir', help='output directory', default='.', show_default=True)
@click.option('--force', help='re-download even if up to date', is_flag=True)
@click.argument('names', nargs=-1)
@click.pass_context
def main(ctx, api_key, outdir, force, names):
    logger = ctx.obj['logger']
    logger.debug(f'input arguments: api_key=***, outdir={outdir}, force={force}, names={names}')

    requested = list(names) if names else list(FILES)
    invalid = [n for n in requested if n not in FILES]
    if invalid:
        logger.error(f'unknown file(s): {invalid}; available: {list(FILES)}')
        exit(1)

    try:
        dl = OmimDownloads(api_key=api_key, outdir=outdir, logger=logger)
    except ApiKeyError as exc:
        click.secho(str(exc), fg='red', err=True)
        exit(1)

    if force:
        downloaded = dl.download(requested, force=True)
    else:
        need = dl.check_updates(requested)
        if not need:
            click.secho('all requested files are up to date', fg='green')
        else:
            click.secho(f'updates available: {need}', fg='yellow')
            downloaded = dl.download(need)

    click.secho('***** OMIM download files *****', fg='yellow', bold=True)
    for name in requested:
        gen = dl.local_generated(name)
        mark = click.style('OK', fg='green') if gen else click.style('MISSING', fg='red')
        click.echo(f'  {name:<10} Generated: {gen or "-":<12} [{mark}]')


if __name__ == '__main__':
    main()
