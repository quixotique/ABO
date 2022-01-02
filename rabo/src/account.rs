use rust_decimal::prelude::*;
use std::fmt;

use crate::money::*;
use crate::tags::*;

#[derive(Debug)]
pub struct Account<'a> {
    name: Box<str>,
    currency: &'static Currency,
    #[allow(dead_code)]
    children: Vec<&'a Account<'a>>,
    tags: Tags,
}

#[derive(Debug)]
pub struct AccountIter<'a> {
    pub this: &'a Account<'a>,
    parent: Option<&'a AccountIter<'a>>,
}

impl<'a> Account<'a> {
    pub fn new<'b, I: Iterator<Item = &'b str>>(name: &'b str, tags: I) -> Account<'a> {
        Account {
            name: name.to_string().into_boxed_str(),
            currency: DEFAULT_CURRENCY,
            children: Vec::new(),
            tags: Tags::from_iter(tags),
        }
    }

    #[allow(dead_code)]
    fn add_child(&mut self, child: &'a Account<'a>) {
        self.children.push(child)
    }

    fn money_from_decimal(&self, amount: Decimal) -> Money {
        Money::from_decimal(amount, self.currency)
    }

    fn money_from_str(&self, text: &str) -> Result<Money, MoneyError> {
        Money::from_str(text, self.currency)
    }

    #[allow(dead_code)]
    pub fn write_to(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}{}", self.name, self.tags)
    }
}

impl<'a> AccountIter<'a> {
    pub fn new(acc: &'a Account<'a>) -> AccountIter<'a> {
        AccountIter {
            this: acc,
            parent: None,
        }
    }

    pub fn money_from_decimal(&self, amount: Decimal) -> Money {
        self.this.money_from_decimal(amount)
    }

    pub fn money_from_str(&self, text: &str) -> Result<Money, MoneyError> {
        self.this.money_from_str(text)
    }
}

impl fmt::Display for AccountIter<'_> {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        if !self.parent.is_none() {
            write!(f, "{}:", self.parent.unwrap())?;
        }
        write!(f, "{}", self.this.name)
    }
}
