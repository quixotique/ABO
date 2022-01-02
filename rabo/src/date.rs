use chrono::format::{DelayedFormat, StrftimeItems};
use chrono::Datelike;

pub type Date = chrono::prelude::NaiveDate;

pub fn format_date<'a>(date: &Date) -> DelayedFormat<StrftimeItems<'a>> {
    date.format("%d/%m/%Y")
}

pub fn format_contextual_date<'a>(date: &Date, context: &Date) -> DelayedFormat<StrftimeItems<'a>> {
    let mut fmt: &'static str = "%d/%m/%Y";
    if date.year() == context.year() {
        fmt = "%d/%m/";
        if date.month() == context.month() {
            fmt = "%d//";
            if date.day() == context.day() {
                fmt = "";
            }
        }
    }
    date.format(fmt)
}
