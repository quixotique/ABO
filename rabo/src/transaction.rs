use std::collections::HashSet;
use chrono::prelude::*;
use rust_decimal::prelude::*;
use rusty_money::{iso};

pub type Money = rusty_money::Money<'static, iso::Currency>;
pub const CURRENCY : &iso::Currency = iso::AUD;

#[derive(Debug)]
#[allow(dead_code)]
pub struct Entry {
    account: String, // TODO: Account
    amount: Money,
    cdate: Option<NaiveDate>,
    detail: String,
}

impl Entry {
    pub fn new(account: String, amount: Decimal, cdate: Option<NaiveDate>, detail: String) -> Entry {
        let entry = Entry{account: account,
                          amount: Money::from_decimal(amount, CURRENCY),
                          cdate: cdate,
                          detail: detail,
                          };
        if entry.amount.is_zero() {
            panic!("zero amount: {:?}", entry)
        }
        entry
    }
}

pub fn sum<'a, I: Iterator<Item = &'a Entry>>(iter: I) -> Money {
    let mut sum = Decimal::new(0, 0);
    for i in iter {
        sum += Money::amount(&i.amount);
    }
    Money::from_decimal(sum, CURRENCY)
}

#[derive(Debug)]
#[allow(dead_code)]
pub struct Transaction {
    date: NaiveDate,
    edate: NaiveDate,
    who: String,
    what: String,
    entries: Vec<Entry>,
    tags: HashSet<String>,
}

impl Transaction {
    pub fn new(date: NaiveDate, edate: Option<NaiveDate>, who: String, what: String, entries: Vec<Entry>, tags: HashSet<String>) -> Transaction {
        if entries.len() < 2 {
            panic!("too few entries")
        }
        if ! sum(entries.iter()).is_zero() {
            panic!("entries do not sum to zero: {:?}", entries)
        }
        Transaction{date: date,
                    edate: match edate { Some(d) => d, None => date },
                    who: who,
                    what: what,
                    entries: entries,
                    tags: tags,
                    }

    }
}
