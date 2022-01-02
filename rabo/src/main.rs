mod account;
mod date;
mod money;
mod tags;
mod transaction;

use crate::account::*;
use crate::date::*;
use crate::transaction::*;
use structopt::StructOpt;

#[derive(Debug, StructOpt)]
#[structopt(name = "rabo", about = "ABO in Rust.")]
struct Rabo {
    /// Print debug output
    #[structopt(short = "q", long)]
    _quiet: bool,

    /// Print debug output
    #[structopt(short = "D", long)]
    debug: bool,

    /// Force recompile of transaction cache
    #[structopt(short = "f", long)]
    _force: bool,

    #[structopt(subcommand)]
    _command: Command,
}

#[derive(Debug, StructOpt)]
enum Command {
    Bsheet {
        #[structopt(flatten)]
        _opts: ReportOpts,
    },

    Profloss {
        #[structopt(flatten)]
        _opts: ReportOpts,
    },
}

#[derive(Debug, StructOpt)]
struct ReportOpts {
    /// Print full account names instead of tree
    #[structopt(long)]
    _fullnames: bool,

    /// Print account labels
    #[structopt(long)]
    _labels: bool,
}

fn main() {
    let opt = Rabo::from_args();
    if opt.debug {
        let a1 = Account::new("A1", vec!["tag11", "tag2"].into_iter());
        let a2 = Account::new("A2", vec![].into_iter());
        let i1 = AccountIter::new(&a1);
        let i2 = AccountIter::new(&a2);
        let t = Transaction::new(
            Date::from_ymd(2021, 12, 29),
            Some(Date::from_ymd(2021, 12, 31)),
            "Who",
            "What",
            vec![
                Entry::new(&i1, "1", Some(Date::from_ymd(2021, 11, 30)), "detail"),
                Entry::new(&i2, "-1", None, "detail"),
            ],
            vec!["tag33", "tag4"].into_iter(),
        );
        println!("{}", t);
    }
}
