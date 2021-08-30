use std::collections::HashSet;
use chrono::prelude::*;
use rusty_money::Money;

struct Entry {
    account: Account,
    amount: Money,
    cdate: Option<Date>,
    detail: String,
}

struct Transaction {
    date: Date,
    edate: Date,
    who: String,
    what: String,
    entries: Vec<Entry>,
    tags: HashSet<String>,
}
