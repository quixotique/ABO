use rust_decimal::prelude::*;
use std::fmt;

use crate::money::*;
use crate::tags::*;

#[derive(Debug)]
pub struct Account<'a> {
    parent: Option<&'a Account<'a>>,
    name: Box<str>,
    currency: &'static Currency,
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
            currency: DEFAULT_CURRENCY,
            tags: Tags::from_iter(tags),
        }
    }

    pub fn money_from_decimal(&self, amount: Decimal) -> Money {
        Money::from_decimal(amount, self.currency)
    }

    pub fn money_from_str(&self, text: &str) -> Result<Money, MoneyError> {
        Money::from_str(text, self.currency)
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
