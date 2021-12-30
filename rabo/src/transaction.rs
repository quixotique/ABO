use chrono::prelude::*;
use rust_decimal::prelude::*;
use rusty_money::iso;
use std::collections::HashSet;
use std::fmt;

pub type Money = rusty_money::Money<'static, iso::Currency>;
pub const CURRENCY: &iso::Currency = iso::AUD;

pub type Tags = HashSet<String>;

#[derive(Debug)]
#[allow(dead_code)]
pub struct Account<'a> {
    parent: Option<&'a Account<'a>>,
    name: String,
    currency: &'static iso::Currency,
    tags: Tags,
}

impl<'a> Account<'a> {
    pub fn new(parent: Option<&'a Account<'a>>, name: String, tags: Tags) -> Account<'a> {
        Account {
            parent: parent,
            name: name,
            currency: CURRENCY,
            tags: tags,
        }
    }
}

impl fmt::Display for Account<'_> {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        if !self.parent.is_none() {
            write!(f, "{}:", self.parent.unwrap())?;
        }
        write!(f, "{}", self.name)
    }
}

#[derive(Debug)]
#[allow(dead_code)]
pub struct Entry<'a> {
    account: &'a Account<'a>,
    amount: Decimal,
    cdate: Option<NaiveDate>,
    detail: String,
}

impl<'a> Entry<'a> {
    pub fn new(
        account: &'a Account,
        amount: &str,
        cdate: Option<NaiveDate>,
        detail: String,
    ) -> Entry<'a> {
        let entry = Entry {
            account: account,
            amount: *Money::from_str(amount, account.currency).unwrap().amount(),
            cdate: cdate,
            detail: detail,
        };
        if entry.amount.is_zero() {
            panic!("zero amount: {:?}", entry)
        }
        entry
    }

    pub fn money(&self) -> Money {
        Money::from_decimal(self.amount, self.account.currency)
    }
}

pub fn sum<'a, I: Iterator<Item = &'a Entry<'a>>>(mut iter: I) -> Money {
    let mut sum = iter.next().unwrap().money();
    for entry in iter {
        sum += entry.money();
    }
    sum
}

impl fmt::Display for Entry<'_> {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}  {}", *self.account, self.amount)?;
        if !self.detail.is_empty() {
            write!(f, " ; {}", self.detail)?;
        }
        Ok(())
    }
}

#[derive(Debug)]
#[allow(dead_code)]
pub struct Transaction<'a> {
    date: NaiveDate,
    edate: NaiveDate,
    who: String,
    what: String,
    entries: Vec<Entry<'a>>,
    tags: Tags,
}

impl<'a> Transaction<'a> {
    pub fn new(
        date: NaiveDate,
        edate: Option<NaiveDate>,
        who: String,
        what: String,
        entries: Vec<Entry<'a>>,
        tags: Tags,
    ) -> Transaction {
        if entries.len() < 2 {
            panic!("too few entries")
        }
        if !sum(entries.iter()).is_zero() {
            panic!("entries do not sum to zero: {:?}", entries)
        }
        Transaction {
            date: date,
            edate: match edate {
                Some(d) => d,
                None => date,
            },
            who: who,
            what: what,
            entries: entries,
            tags: tags,
        }
    }
}

impl fmt::Display for Transaction<'_> {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}", self.date)?;
        if !self.who.is_empty() {
            if !self.what.is_empty() {
                write!(f, " {}; {}", self.who, self.what)?;
            } else {
                write!(f, " {}", self.who)?;
            }
        } else if !self.what.is_empty() {
            write!(f, " ; {}", self.what)?;
        }
        writeln!(f)?;
        for entry in &self.entries {
            writeln!(f, "   {}", entry)?;
        }
        Ok(())
    }
}
