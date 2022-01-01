use chrono::prelude::*;
use rust_decimal::prelude::*;
use rusty_money::iso;
use std::boxed::Box;
use std::collections::HashSet;
use std::fmt;

pub type Money = rusty_money::Money<'static, iso::Currency>;

pub const CURRENCY: &iso::Currency = iso::AUD;

#[derive(Default, Debug)]
struct Tags {
    inner: HashSet<Box<str>>,
}

impl Tags {
    fn from_iter<'a, I: Iterator<Item = &'a str>>(iter: I) -> Tags {
        let mut tags = Tags::default();
        for s in iter {
            tags.inner.insert(s.to_string().into_boxed_str());
        }
        tags
    }
}

impl fmt::Display for Tags {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        let mut vec = self.inner.iter().collect::<Vec<&Box<str>>>();
        vec.sort_by(|a, b| human_sort::compare(*a, *b));
        for tag in vec {
            write!(f, " ={}", tag)?;
        }
        Ok(())
    }
}

#[derive(Debug)]
pub struct Account<'a> {
    parent: Option<&'a Account<'a>>,
    name: Box<str>,
    currency: &'static iso::Currency,
    tags: Tags,
}

impl<'a> Account<'a> {
    pub fn new<'b, I: Iterator<Item = &'b str>>(
        parent: Option<&'a Account<'a>>,
        name: &'b str,
        tags: I,
    ) -> Account<'a> {
        Account {
            parent,
            name: name.to_string().into_boxed_str(),
            currency: CURRENCY,
            tags: Tags::from_iter(tags),
        }
    }

    #[allow(dead_code)]
    pub fn write_to(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}{}", self, self.tags)
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
pub struct Entry<'a> {
    account: &'a Account<'a>,
    amount: Decimal,
    cdate: Option<NaiveDate>,
    detail: &'a str,
}

impl<'a> Entry<'a> {
    pub fn new(
        account: &'a Account,
        amount_str: &str,
        cdate: Option<NaiveDate>,
        detail: &'a str,
    ) -> Entry<'a> {
        let money = Money::from_str(amount_str, account.currency);
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
            detail,
        };
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
        if !self.cdate.is_none() {
            write!(f, " {{{}}}", self.cdate.unwrap())?;
        }
        Ok(())
    }
}

#[derive(Debug)]
pub struct Transaction<'a> {
    date: NaiveDate,
    edate: NaiveDate,
    who: &'a str,
    what: &'a str,
    entries: Vec<Entry<'a>>,
    tags: Tags,
}

impl<'a> Transaction<'a> {
    pub fn new<'b, I: Iterator<Item = &'b str>>(
        date: NaiveDate,
        edate: Option<NaiveDate>,
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
            who,
            what,
            entries,
            tags: Tags::from_iter(tags),
        }
    }
}

impl fmt::Display for Transaction<'_> {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}", self.date)?;
        if self.edate != self.date {
            write!(f, "={}", self.edate)?;
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
            writeln!(f, "   {}", entry)?;
        }
        Ok(())
    }
}
