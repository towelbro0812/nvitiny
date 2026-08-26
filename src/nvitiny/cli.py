"""命令列進入點。

不帶任何參數就是即時模式，並自動貼合終端目前的寬高。
導進管線（非 TTY）時自動退回單次輸出。
"""

from __future__ import annotations

import argparse


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="nvitiny",
        description="窄終端機優先的 NVIDIA GPU 監看工具。不帶參數即為即時模式。",
    )
    parser.add_argument("-1", "--once", action="store_true", help="輸出一次就結束")
    parser.add_argument(
        "-i", "--interval", type=float, default=1.0, metavar="秒",
        help="即時模式的取樣間隔（預設 1.0）",
    )
    parser.add_argument(
        "--demo", action="store_true",
        help="用內建 fixture 把各種寬度都畫一遍，不需要 GPU",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.demo:
        from .app import demo

        return demo.run()

    from .app import live, once
    from .core.sample import from_live

    # 非 TTY（例如導進管線）做不到即時重繪，自動退回單次輸出
    if not args.once and live.supported():
        try:
            return live.run(from_live, args.interval)
        except KeyboardInterrupt:
            return 130

    return once.run(from_live)


if __name__ == "__main__":
    raise SystemExit(main())
