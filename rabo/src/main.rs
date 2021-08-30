use structopt::StructOpt;

#[derive(Debug, StructOpt)]
#[structopt(name = "rabo", about = "ABO in Rust.")]
struct Rabo {
    /// Print debug output
    #[structopt(short = "q", long)]
    quiet: bool,

    /// Print debug output
    #[structopt(short = "D", long)]
    debug: bool,

    /// Force recompile of transaction cache
    #[structopt(short = "f", long)]
    force: bool,

    #[structopt(subcommand)]
    command: Command,
}

#[derive(Debug, StructOpt)]
enum Command {
    Bsheet {
        #[structopt(flatten)]
        opts: ReportOpts
    },

    Profloss {
        #[structopt(flatten)]
        opts: ReportOpts
    },
}

#[derive(Debug, StructOpt)]
struct ReportOpts {
    /// Print full account names instead of tree
    #[structopt(long)]
    fullnames: bool,

    /// Print account labels
    #[structopt(long)]
    labels: bool,
}

fn main() {
    let opt = Rabo::from_args();
    if opt.debug {
        println!("Debug!");
    }
}
