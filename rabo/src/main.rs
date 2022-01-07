mod account;
mod date;
mod money;
mod tags;
mod transaction;

use crate::account::*;
use crate::date::*;
use crate::transaction::*;
use std::fs::File;
use structopt::StructOpt;

#[macro_use]
extern crate lazy_static;

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

fn main() -> Result<(), Box<dyn std::error::Error>> {
    env_logger::init();

    let opt = Rabo::from_args();
    if opt.debug {
        let mut chart = Chart::new();
        chart.read_from(File::open("./test/accounts")?)?;
        chart.write_to(&mut std::io::stdout())?;
        chart
            .add_top_level_account(
                "A1",
                vec!["labelA1"].into_iter(),
                vec!["tag11", "tag2"].into_iter(),
            )
            .add_child("x", vec!["label_x"].into_iter(), vec!["foo"].into_iter())
            .add_child("y", vec!["label_y"].into_iter(), vec!["bar"].into_iter());
        chart.add_top_level_account("A2", vec!["labelA2"].into_iter(), vec![].into_iter());
        let t = Transaction::new(
            Date::from_ymd(2021, 12, 29),
            Some(Date::from_ymd(2021, 12, 31)),
            "Who",
            "What",
            vec![
                Entry::new(
                    chart.get_account("A1:x:y").unwrap(),
                    "1",
                    Some(Date::from_ymd(2021, 11, 30)),
                    "detail",
                ),
                Entry::new(chart.get_account("A2").unwrap(), "-1", None, "detail"),
            ],
            vec!["tag33", "tag4"].into_iter(),
        );
        println!("{}", t);
    }
    Ok(())
}
