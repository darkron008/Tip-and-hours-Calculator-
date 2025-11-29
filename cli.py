"""Simple CLI for the Tip-and-hours-Calculator project.

Usage examples (PowerShell):
  python cli.py tip --amount 100 --percent 15
  python cli.py pay --hours 40 --rate 15.50
"""
from argparse import ArgumentParser
from decimal import Decimal
from calculator.core import calculate_tip, calculate_total, calculate_pay


def main():
    parser = ArgumentParser(prog="tip-hours")
    sub = parser.add_subparsers(dest="cmd")

    p_tip = sub.add_parser("tip", help="Calculate tip and total")
    p_tip.add_argument("--amount", required=True, help="Base amount (e.g., 100.00)")
    p_tip.add_argument("--percent", required=True, help="Tip percent (e.g., 15)")

    p_pay = sub.add_parser("pay", help="Calculate pay from hours and rate")
    p_pay.add_argument("--hours", required=True, help="Hours worked (e.g., 40)")
    p_pay.add_argument("--rate", required=True, help="Hourly rate (e.g., 15.50)")

    args = parser.parse_args()
    if args.cmd == "tip":
        amount = Decimal(args.amount)
        percent = Decimal(args.percent)
        tip = calculate_tip(amount, percent)
        total = calculate_total(amount, percent)
        print(f"Amount: {amount:.2f}")
        print(f"Tip ({percent}%): {tip:.2f}")
        print(f"Total: {total:.2f}")
    elif args.cmd == "pay":
        hours = Decimal(args.hours)
        rate = Decimal(args.rate)
        pay = calculate_pay(hours, rate)
        print(f"Hours: {hours}")
        print(f"Rate: {rate:.2f}")
        print(f"Pay: {pay:.2f}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
