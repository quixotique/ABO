use regex::Regex;
use rust_decimal::prelude::*;
use std::fmt;
use std::io::BufRead;
use std::iter::FromIterator;
use std::ptr;

use crate::money::*;
use crate::tags::*;

const NAME_SEPARATOR: &str = ":";

#[derive(Debug)]
pub struct Account {
    name: Box<str>,
    currency: &'static Currency,
    parent: *const Account,
    children: Vec<Box<Account>>, // Box guarantees stable address for unsafe parent ptr
    labels: Labels,
    tags: Tags,
}

impl Account {
    fn is_valid_name(name: &str) -> bool {
        !name.is_empty()
            && !name.contains(NAME_SEPARATOR)
            && !name.contains("  ")
            && !name.starts_with(" ")
            && !name.ends_with(" ")
    }

    fn new<'b, T: Iterator<Item = &'b str>>(name: &'b str, labels: T, tags: T) -> Account {
        assert!(Account::is_valid_name(name), "name = {:?}", name);
        Account {
            name: name.to_string().into_boxed_str(),
            currency: DEFAULT_CURRENCY,
            children: vec![],
            parent: ptr::null(),
            labels: Labels::from_iter(labels),
            tags: Tags::from_iter(tags),
        }
    }

    pub fn money_from_decimal(&self, amount: Decimal) -> Money {
        Money::from_decimal(amount, self.currency)
    }

    pub fn money_from_str(&self, text: &str) -> Result<Money, MoneyError> {
        Money::from_str(text, self.currency)
    }

    pub fn add_child<'a, 'b, T: Iterator<Item = &'b str>>(
        &mut self,
        name: &'b str,
        labels: T,
        tags: T,
    ) -> &mut Account {
        let mut acc = Account::new(name, labels, tags);
        acc.parent = self;
        self.children.push(Box::new(acc));
        self.children.last_mut().unwrap()
    }

    pub fn get_child(&self, name: &str) -> Option<&Account> {
        match self.children.iter().find(|&a| *a.name == *name) {
            Some(acc) => Some(&*acc),
            None => None,
        }
    }

    fn traverse<E>(&self, f: &mut impl FnMut(&Account) -> Result<(), E>) -> Result<(), E> {
        f(self)?;
        for acc in self.children.iter() {
            acc.traverse(f)?;
        }
        Ok(())
    }
}

impl fmt::Display for Account {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        if !self.parent.is_null() {
            write!(f, "{}:", unsafe { &*self.parent })?;
        }
        write!(f, "{}", self.name)
    }
}

#[derive(Debug)]
pub struct Chart {
    top_level: Vec<Box<Account>>,
}

lazy_static! {
    static ref LABEL_RE: Regex = Regex::new(r"\[(\S+)]").unwrap();
    static ref TAG_RE: Regex = Regex::new(r"=(\S+)").unwrap();
}

impl Chart {
    pub fn new() -> Chart {
        Chart { top_level: vec![] }
    }

    pub fn get_account(&self, full_name: &str) -> Option<&Account> {
        let mut iter = full_name.split(NAME_SEPARATOR);
        let first_name = iter.next()?;
        let mut acc: &Account = self.top_level.iter().find(|&a| *a.name == *first_name)?;
        for name in iter {
            acc = acc.get_child(name)?;
        }
        Some(acc)
    }

    fn traverse<E>(&self, f: &mut impl FnMut(&Account) -> Result<(), E>) -> Result<(), E> {
        for acc in &self.top_level {
            acc.traverse(f)?
        }
        Ok(())
    }

    fn get_last_account(&mut self, depth: usize) -> &mut Account {
        let mut accounts: &mut Vec<Box<Account>> = &mut self.top_level;
        for _level in 0..depth {
            accounts = &mut accounts.last_mut().unwrap().children;
        }
        accounts.last_mut().unwrap()
    }

    pub fn add_top_level_account<'b, T: Iterator<Item = &'b str>>(
        &mut self,
        name: &'b str,
        labels: T,
        tags: T,
    ) -> &mut Account {
        self.top_level
            .push(Box::new(Account::new(name, labels, tags)));
        self.top_level.last_mut().unwrap()
    }

    fn extract_matches<'a>(text: &'a str, rexp: &Regex) -> (String, Vec<&'a str>) {
        let mut ret_str = "".to_string();
        let mut ret_vec = vec![];
        let mut end: usize = 0;
        let mut grow = |frag: &str| {
            let tfrag = frag.trim();
            if !tfrag.is_empty() {
                if !ret_str.is_empty() {
                    ret_str += " ";
                }
                ret_str += tfrag;
            }
        };
        for cap in rexp.captures_iter(&text) {
            ret_vec.push(cap.get(1).unwrap().as_str());
            let all = cap.get(0).unwrap();
            grow(&text[end..all.start()]);
            end = all.end();
        }
        grow(&text[end..]);
        (ret_str, ret_vec)
    }

    pub fn read_from<R: std::io::Read>(&mut self, reader: R) -> Result<(), std::io::Error> {
        struct Level {
            indent: Box<str>,
        }
        let mut stack: Vec<Level> = vec![];
        for result in std::io::BufReader::new(reader).lines() {
            let line = result?;
            let text = line.trim_start();
            if text.starts_with("#") || text.is_empty() {
                continue;
            }
            let indent = &line[..(line.len() - text.len())];
            while !stack.is_empty() && stack.last().unwrap().indent.starts_with(indent) {
                stack.pop();
            }
            if !if stack.is_empty() {
                indent.is_empty()
            } else {
                indent.starts_with(&*stack.last().unwrap().indent)
            } {
                return Err(std::io::Error::new(
                    std::io::ErrorKind::InvalidInput,
                    "bad indent",
                ));
            }
            let (name1, tags) = Chart::extract_matches(text, &TAG_RE);
            let (name, labels) = Chart::extract_matches(&name1, &LABEL_RE);
            if stack.is_empty() {
                self.add_top_level_account(&name, labels.into_iter(), tags.into_iter());
            } else {
                self.get_last_account(stack.len() - 1).add_child(
                    &name,
                    labels.into_iter(),
                    tags.into_iter(),
                );
            };
            stack.push(Level {
                indent: indent.to_string().into_boxed_str(),
            });
        }
        Ok(())
    }

    #[allow(dead_code)]
    pub fn write_to<W: std::io::Write>(&self, writer: &mut W) -> Result<(), std::io::Error> {
        self.traverse(&mut |acc| writeln!(writer, "{}{}{}", acc, acc.labels, acc.tags))
    }
}
