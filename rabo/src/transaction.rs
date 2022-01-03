use rust_decimal::prelude::*;
use std::fmt;

use crate::account::*;
use crate::date::*;
use crate::money::*;
use crate::tags::*;

#[derive(Debug)]
pub struct Entry<'a> {
    account: &'a Account,
    amount: Decimal,
    cdate: Option<Date>,
    detail: Box<str>,
}

impl<'a> Entry<'a> {
    pub fn new(
        account: &'a Account,
        amount_str: &str,
        cdate: Option<Date>,
        detail: &'a str,
    ) -> Entry<'a> {
        let money = account.money_from_str(amount_str);
        if money.is_err() {
            panic!("malformed amount: {:?}", amount_str)
        }
        let amount = money.as_ref().unwrap().amount();
        if amount.is_zero() {
            panic!("zero amount is invalid: {:?}", money)
        }
        let entry = Entry {
            account,
            amount: *amount,
            cdate,
            detail: detail.to_string().into_boxed_str(),
        };
        entry
    }

    pub fn money(&self) -> Money {
        self.account.money_from_decimal(self.amount)
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
        write!(f, "{}  {}", self.account, self.amount)?;
        if !self.detail.is_empty() {
            write!(f, " ; {}", self.detail)?;
        }
        Ok(())
    }
}

#[derive(Debug)]
struct ContextualEntry<'a> {
    entry: &'a Entry<'a>,
    context: &'a Transaction<'a>,
}

impl fmt::Display for ContextualEntry<'_> {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}", self.entry)?;
        if !self.entry.cdate.is_none() {
            write!(
                f,
                " {{{}}}",
                format_contextual_date(&self.entry.cdate.unwrap(), &self.context.date)
            )?;
        }
        Ok(())
    }
}

#[derive(Debug)]
pub struct Transaction<'a> {
    date: Date,
    edate: Date,
    who: Box<str>,
    what: Box<str>,
    entries: Vec<Entry<'a>>,
    tags: Tags,
}

impl<'a> Transaction<'a> {
    pub fn new<'b, I: Iterator<Item = &'b str>>(
        date: Date,
        edate: Option<Date>,
        who: &'a str,
        what: &'a str,
        entries: Vec<Entry<'a>>,
        tags: I,
    ) -> Transaction<'a> {
        if entries.len() < 2 {
            panic!("too few entries")
        }
        if !sum(entries.iter()).is_zero() {
            panic!("entries do not sum to zero: {:?}", entries)
        }
        Transaction {
            date,
            edate: match edate {
                Some(d) => d,
                None => date,
            },
            who: who.to_string().into_boxed_str(),
            what: what.to_string().into_boxed_str(),
            entries,
            tags: Tags::from_iter(tags),
        }
    }
}

impl fmt::Display for Transaction<'_> {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}", format_date(&self.date))?;
        if self.edate != self.date {
            write!(f, "={}", format_contextual_date(&self.edate, &self.date))?;
        }
        if !self.who.is_empty() {
            if !self.what.is_empty() {
                write!(f, " {}; {}", self.who, self.what)?;
            } else {
                write!(f, " {}", self.who)?;
            }
        } else if !self.what.is_empty() {
            write!(f, " ; {}", self.what)?;
        }
        write!(f, "{}", self.tags)?;
        writeln!(f)?;
        for entry in &self.entries {
            writeln!(
                f,
                "   {}",
                ContextualEntry {
                    entry: entry,
                    context: self,
                }
            )?;
        }
        Ok(())
    }
}
