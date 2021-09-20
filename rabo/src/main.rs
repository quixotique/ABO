use rust_decimal::prelude::*;
use std::collections::HashSet;
use std::iter::FromIterator;
use chrono::prelude::*;
use structopt::StructOpt;

mod transaction;

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
        _opts: ReportOpts
    },

    Profloss {
        #[structopt(flatten)]
        _opts: ReportOpts
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
        let t = transaction::Transaction::new(NaiveDate::from_ymd(2021, 12, 29),
                                              None,
                                              "Who".to_string(),
                                              "What".to_string(),
                                              vec![transaction::Entry::new("account A".to_string(), Decimal::new(1, 0), None, "detail".to_string()),
                                                   transaction::Entry::new("account B".to_string(), Decimal::new(-1, 0), None, "detail".to_string())
                                                  ],
                                              HashSet::from_iter(vec![]));
        println!("transaction {:?}", t);
    }
}
