use rust_decimal::prelude::*;
use std::fmt;
use std::ptr;

use crate::money::*;
use crate::tags::*;

const NAME_SEPARATOR: &str = ":";

#[derive(Debug)]
pub struct Account {
    name: Box<str>,
    currency: &'static Currency,
    parent: *const Account,
    children: Vec<Account>,
    #[allow(dead_code)]
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

    fn new<'b, T: Iterator<Item = &'b str>>(name: &'b str, tags: T) -> Account {
        assert!(Account::is_valid_name(name));
        Account {
            name: name.to_string().into_boxed_str(),
            currency: DEFAULT_CURRENCY,
            children: vec![],
            parent: ptr::null(),
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
        tags: T,
    ) -> &mut Account {
        let mut acc = Account::new(name, tags);
        acc.parent = self;
        self.children.push(acc);
        self.children.last_mut().unwrap()
    }

    pub fn get_child(&self, name: &str) -> Option<&Account> {
        self.children.iter().find(|&a| *a.name == *name)
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
    top_level: Vec<Account>,
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

    pub fn add_top_level_account<'b, T: Iterator<Item = &'b str>>(
        &mut self,
        name: &'b str,
        tags: T,
    ) -> &mut Account {
        self.top_level.push(Account::new(name, tags));
        self.top_level.last_mut().unwrap()
    }
}
