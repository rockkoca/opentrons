import server
from argparse import ArgumentParser


def server_arg_parser():
    arg_parser = ArgumentParser(
            description="Opentrons application server",
            prog="opentrons.server.main",
            add_help=False
    )
    arg_parser.add_argument(
        "-H", "--hostname",
        help="TCP/IP hostname to serve on (default: %(default)r)",
        default="localhost"
    )
    arg_parser.add_argument(
        "-P", "--port",
        help="TCP/IP port to serve on (default: %(default)r)",
        type=int,
        default="8080"
    )
    arg_parser.add_argument(
        "-U", "--path",
        help="Unix file system path to serve on. Specifying a path will cause "
             "hostname and port arguments to be ignored.",
    )

    return arg_parser


def main():
    arg_parser = server_arg_parser()
    args = arg_parser.parse_args()
    server.run(args.hostname, args.port, args.path)
    # Super basic level logging setup
    arg_parser.exit(message="Stopped\n")


if __name__ == "__main__":
    main()
